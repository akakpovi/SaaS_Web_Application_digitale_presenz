import logging
import random
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from monitoring.models import INTERVAL_MAP, MonitoringConfig
from subscriptions.services.quotas import (
    get_effective_plan,
    get_effective_plan_for_organization,
    scans_used_this_month,
)

logger = logging.getLogger(__name__)


def _plan_for(website):
    """Return the plan that limits scheduled scans for *website*.

    Team quotas are paid by the organization's billing owner, exactly like the
    API's ``assert_can_scan``; a personal website falls back to its owner.
    """
    organization = getattr(website, "organization", None)
    if organization is not None:
        return get_effective_plan_for_organization(organization)
    return get_effective_plan(website.owner)


def _quota_scope(website) -> dict:
    """Usage filter matching the plan scope (organization or owner)."""
    organization = getattr(website, "organization", None)
    if organization is not None:
        return {"organization": organization}
    return {"user": website.owner}


def _reschedule(config: MonitoringConfig, *, now, next_scan_at) -> bool:
    """Persist a new schedule **only if the config is still enabled**.

    The scheduler loads a batch and writes ``next_scan_at`` at the end of each
    iteration.  Without this guard, pausing a website while a tick is running
    left a fresh ``next_scan_at`` on a disabled config: nothing scanned it
    again, but the dashboard showed a next check that could never happen.
    Returns True when the schedule was written.
    """
    updated = MonitoringConfig.objects.filter(pk=config.pk, enabled=True).update(
        last_scan_at=now,
        next_scan_at=next_scan_at,
        updated_at=now,
    )
    if updated:
        config.last_scan_at = now
        config.next_scan_at = next_scan_at
    return bool(updated)


def _effective_interval(config: MonitoringConfig, plan) -> timedelta:
    """Configured interval, never shorter than the plan's minimum."""
    interval = INTERVAL_MAP.get(config.interval, timedelta(hours=24))
    if plan is None:
        return interval
    minimum = INTERVAL_MAP.get(plan.min_scan_interval)
    if minimum is None:
        return interval
    return max(interval, minimum)


@shared_task(name="monitoring.tasks.run_due_monitors")
def run_due_monitors() -> dict:
    """
    Periodic task (every 5 min):
    1. Find MonitoringConfig with next_scan_at <= now
    2. Skip muted websites and websites that already have an active scan
    3. Queue a new Scan using the website's configured scan type
    4. Schedule next_scan_at with jitter

    The scan type comes from ``MonitoringConfig.scan_type``: ``health`` keeps
    the historical passive behaviour, ``security``/``full`` opt into the
    external scanners (ZAP, Nuclei, …) for that website only.

    The number of scans queued per run is capped so a large fleet coming due
    at the same minute cannot flood the Celery queue and the scan workers.
    """
    from alerts.models import MuteWindow
    from scans.models import Scan
    from scans.tasks import run_authenticated_scan

    now = timezone.now()
    configs = MonitoringConfig.objects.filter(
        enabled=True,
        next_scan_at__lte=now,
    ).select_related(
        "website", "website__owner", "website__organization"
    ).order_by("next_scan_at")

    max_per_run = max(1, int(getattr(settings, "MONITORING_MAX_SCANS_PER_RUN", 20)))
    queued, skipped, active, quota_blocked = 0, 0, 0, 0
    quota_usage: dict[str, int] = {}

    for config in configs:
        if queued >= max_per_run:
            logger.warning(
                "run_due_monitors: per-run cap reached (%d); remaining "
                "websites stay due until the next tick",
                max_per_run,
            )
            break

        website = config.website

        # Never queue a second scan for a website that is already scanning.
        if Scan.objects.filter(
            website=website,
            status__in=[
                Scan.Status.PENDING,
                Scan.Status.QUEUED,
                Scan.Status.RUNNING,
            ],
        ).exists():
            _reschedule(config, now=now, next_scan_at=now + timedelta(minutes=15))
            active += 1
            logger.info(
                "Skipped %s: a scan is already active", website.domain
            )
            continue

        # Mute window check
        active_mutes = MuteWindow.objects.filter(
            user=website.owner,
            is_active=True,
            start_at__lte=now,
            end_at__gte=now,
        )
        if (
            active_mutes.filter(websites__isnull=True).exists()
            or active_mutes.filter(websites=website).exists()
        ):
            _reschedule(config, now=now, next_scan_at=now + timedelta(hours=1))
            skipped += 1
            logger.info("Skipped muted website %s", website.domain)
            continue

        # Enforce the billing plan: no scheduled scan beyond the monthly quota,
        # and never shorter than the plan's minimum interval.  Without this,
        # monitoring silently bypassed every limit enforced on the API.
        plan = _plan_for(website)
        scope = _quota_scope(website)
        scope_key = (
            f"org:{scope['organization'].pk}"
            if "organization" in scope
            else f"user:{scope['user'].pk}"
        )
        if plan is not None:
            if scope_key not in quota_usage:
                quota_usage[scope_key] = scans_used_this_month(**scope)
            if quota_usage[scope_key] >= plan.max_scans_per_month:
                # Retry tomorrow: the quota may reset on the 1st, and a daily
                # retry avoids a tight loop while staying responsive.
                _reschedule(config, now=now, next_scan_at=now + timedelta(days=1))
                quota_blocked += 1
                logger.warning(
                    "Skipped %s: monthly scan quota reached (%d/%d)",
                    website.domain,
                    quota_usage[scope_key],
                    plan.max_scans_per_month,
                )
                continue

        # Create and queue scan with the website's configured policy.
        scan = Scan.objects.create(
            website=website,
            trigger=Scan.Trigger.MONITORING,
            status=Scan.Status.QUEUED,
            scan_type=config.scan_type,
        )
        run_authenticated_scan.delay(scan.id)

        if plan is not None:
            quota_usage[scope_key] += 1

        # Schedule next with jitter, respecting the plan's minimum interval.
        interval_td = _effective_interval(config, plan)
        jitter = timedelta(minutes=random.randint(0, 5))
        _reschedule(config, now=now, next_scan_at=now + interval_td + jitter)
        queued += 1

        logger.info(
            "Queued monitoring scan %s for %s type=%s (next: %s)",
            scan.id, website.domain, scan.scan_type, config.next_scan_at,
        )

    logger.info(
        "run_due_monitors: queued=%d skipped=%d active=%d quota_blocked=%d",
        queued,
        skipped,
        active,
        quota_blocked,
    )
    return {
        "queued": queued,
        "skipped": skipped,
        "active": active,
        "quota_blocked": quota_blocked,
    }
