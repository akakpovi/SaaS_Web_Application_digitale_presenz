"""Application stricte des quotas de l'offre.

Les limites vivent en base (``Plan``) et sont exposées par l'API, mais tant
qu'aucune vue ne les vérifie, l'offre premium est purement cosmétique.  Ce
module est l'unique point d'entrée utilisé par les vues et les tâches.

Règles :

* un abonnement absent, annulé ou expiré retombe sur les quotas **Free** ;
* ``past_due`` conserve l'offre payante jusqu'à la fin de la période en cours ;
* toute dépassement renvoie un **403** structuré (``code``, ``limit``, ``usage``)
  que le frontend peut afficher et relier à la page de facturation.
"""

from __future__ import annotations

from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

from subscriptions.models import Plan, Subscription


class QuotaExceeded(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Plan quota exceeded."
    default_code = "quota_exceeded"

    def __init__(self, code: str, message: str, **extra):
        self.detail = {"detail": message, "code": code, **extra}


def get_free_plan() -> Plan | None:
    return Plan.objects.filter(tier=Plan.Tier.FREE).first()


def _paid_period_has_ended(sub: Subscription) -> bool:
    """True when the paid period is over (or the row is explicitly expired).

    ``current_period_end`` is NULL for subscriptions created before billing
    was wired (and for provider-less installs): those keep their access, which
    preserves historical accounts.  Once a period end is known, a missed
    renewal (webhook lost, payment failed for weeks) must fall back to Free
    instead of granting the paid tier forever.
    """
    if sub.status == Subscription.Status.EXPIRED:
        return True
    if sub.current_period_end is None:
        return False
    return sub.current_period_end <= timezone.now()


def get_effective_plan(user) -> Plan | None:
    """Return the plan whose limits actually apply to *user* right now.

    The relation is queried explicitly instead of using ``user.subscription``:
    Django caches the reverse one-to-one on the user instance, so a plan
    updated by a webhook after the instance was loaded would otherwise be
    ignored for the whole request.
    """
    sub = (
        Subscription.objects.select_related("plan")
        .filter(user_id=user.pk)
        .first()
    )
    if sub is None:
        return get_free_plan()

    if sub.plan.tier == Plan.Tier.FREE:
        return sub.plan

    if sub.status in {
        Subscription.Status.ACTIVE,
        Subscription.Status.TRIALING,
        Subscription.Status.PAST_DUE,
        Subscription.Status.CANCELLED,
    } and not _paid_period_has_ended(sub):
        # CANCELLED keeps the paid tier until the period the customer already
        # paid for is over; PAST_DUE does the same while Paddle retries the
        # payment.  After the period end, all of them fall back to Free.
        return sub.plan

    return get_free_plan()


def get_effective_plan_for_organization(organization) -> Plan | None:
    """Return the billing plan that applies to *organization*.

    Team quotas are paid by the organization's billing owner, not by the
    analyst who happens to launch a scan.  A shared organization without a
    billing owner has no plan and therefore no enforced ceiling.
    """
    if organization is None or organization.billing_owner_id is None:
        return None
    return get_effective_plan(organization.billing_owner)


def month_start():
    now = timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def scans_used_this_month(user=None, *, organization=None) -> int:
    from scans.models import Scan

    qs = Scan.objects.filter(created_at__gte=month_start())
    if organization is not None:
        qs = qs.filter(website__organization=organization)
    elif user is not None:
        qs = qs.filter(website__owner=user)
    else:
        return 0
    return qs.count()


def websites_used(user=None, *, organization=None) -> int:
    from websites.models import Website

    if organization is not None:
        return Website.objects.filter(organization=organization).count()
    if user is None:
        return 0
    return Website.objects.filter(owner=user).count()


def alert_channels_used(user) -> int:
    from notifications.models import NotificationChannel

    return NotificationChannel.objects.filter(user=user).count()


def usage_snapshot(user) -> dict:
    return {
        "websites": websites_used(user),
        "scans_this_month": scans_used_this_month(user),
        "alert_channels": alert_channels_used(user),
    }


def plan_snapshot(user) -> dict:
    """Limits + current usage, embedded in ``GET /subscriptions/me/``."""
    plan = get_effective_plan(user)
    if plan is None:
        return {"limits": None, "usage": usage_snapshot(user)}
    return {
        "plan_tier": plan.tier,
        "limits": {
            "max_websites": plan.max_websites,
            "max_scans_per_month": plan.max_scans_per_month,
            "max_alert_channels": plan.max_alert_channels,
            "max_team_members": plan.max_team_members,
            "can_export_reports": plan.can_export_reports,
            "can_use_api": plan.can_use_api,
            "can_add_team_members": plan.can_add_team_members,
            "min_scan_interval": plan.min_scan_interval,
        },
        "usage": usage_snapshot(user),
    }


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------


def assert_can_add_website(user, organization=None) -> None:
    if organization is not None:
        plan = get_effective_plan_for_organization(organization)
        used = websites_used(organization=organization)
    else:
        plan = get_effective_plan(user)
        used = websites_used(user)
    if plan is None:
        return
    if used >= plan.max_websites:
        raise QuotaExceeded(
            "website_limit_reached",
            f"Your {plan.name} plan allows {plan.max_websites} website(s). "
            "Upgrade your plan to add more.",
            limit=plan.max_websites,
            usage=used,
            plan=plan.tier,
            upgrade_url="/app/billing",
        )


def assert_can_scan(user, organization=None) -> None:
    if organization is not None:
        plan = get_effective_plan_for_organization(organization)
        used = scans_used_this_month(organization=organization)
    else:
        plan = get_effective_plan(user)
        used = scans_used_this_month(user)
    if plan is None:
        return
    if used >= plan.max_scans_per_month:
        raise QuotaExceeded(
            "scan_quota_exceeded",
            f"Your {plan.name} plan allows {plan.max_scans_per_month} scans "
            "per month. Upgrade your plan for more scans.",
            limit=plan.max_scans_per_month,
            usage=used,
            plan=plan.tier,
            upgrade_url="/app/billing",
        )


def assert_can_add_team_member(organization, include_pending: bool = True) -> None:
    """Enforce the billing owner's team-seat limit for *organization*.

    Pending invitations reserve a seat, so an owner cannot invite more people
    than the plan can ever accommodate.  When an invitation is being accepted
    the caller passes ``include_pending=False`` to avoid counting the seat
    twice.
    """
    plan = get_effective_plan_for_organization(organization)
    if plan is None:
        return
    if not plan.can_add_team_members:
        raise QuotaExceeded(
            "team_members_not_allowed",
            f"Your {plan.name} plan does not include team members. "
            "Upgrade your plan to invite collaborators.",
            plan=plan.tier,
            upgrade_url="/app/billing",
        )

    used = organization.memberships.count()
    if include_pending:
        from organizations.models import OrganizationInvitation

        used += OrganizationInvitation.objects.filter(
            organization=organization,
            status=OrganizationInvitation.Status.PENDING,
        ).count()

    if used >= plan.max_team_members:
        raise QuotaExceeded(
            "team_member_limit_reached",
            f"Your {plan.name} plan allows {plan.max_team_members} team "
            "member(s). Upgrade your plan to invite more.",
            limit=plan.max_team_members,
            usage=used,
            plan=plan.tier,
            upgrade_url="/app/billing",
        )


def assert_can_add_alert_channel(user) -> None:
    plan = get_effective_plan(user)
    if plan is None:
        return
    used = alert_channels_used(user)
    if used >= plan.max_alert_channels:
        raise QuotaExceeded(
            "alert_channel_limit_reached",
            f"Your {plan.name} plan allows {plan.max_alert_channels} alert "
            "channel(s). Upgrade your plan to add more.",
            limit=plan.max_alert_channels,
            usage=used,
            plan=plan.tier,
            upgrade_url="/app/billing",
        )


def assert_paid_plan(user) -> None:
    """Guard the advanced suites (SEO, reputation, security).

    Those scanners run extra outbound work against a target, so they are part
    of every paid tier.  Reads stay open (a downgraded account keeps its
    history), but launching a new run is refused for Free with the same
    structured 403 shape as the other quotas, so the frontend can open the
    upgrade panel from the response alone.
    """
    plan = get_effective_plan(user)
    if plan is None or plan.tier != Plan.Tier.FREE:
        return
    raise QuotaExceeded(
        "paid_plan_required",
        "This feature requires a paid plan. Your current plan is "
        f"{plan.name}.",
        plan=plan.tier,
        required_plan="pro",
        upgrade_url="/app/billing",
    )


def assert_feature(user, feature: str) -> None:
    """Raise when the effective plan does not include *feature*."""
    plan = get_effective_plan(user)
    if plan is None:
        return
    if not getattr(plan, feature, False):
        labels = {
            "can_export_reports": "PDF report export",
            "can_use_api": "API access",
            "can_add_team_members": "team members",
        }
        raise QuotaExceeded(
            f"{feature}_required",
            f"{labels.get(feature, feature)} requires a paid plan. "
            f"Your current plan is {plan.name}.",
            plan=plan.tier,
            upgrade_url="/app/billing",
        )
