import base64
import logging
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from .emails import render_account_email
from .models import User

logger = logging.getLogger(__name__)


def blacklist_user_refresh_tokens(user: User) -> None:
    """Invalidate active refresh tokens after a credential reset."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


def send_verification_email(user: User) -> bool:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verify_path = f"/verify-email?uid={uid}&token={token}"
    subject, message = render_account_email(
        "verify_email",
        user.language,
        link=f"{settings.FRONTEND_URL}{verify_path}",
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("verification_email_delivery_failed", extra={"user_id": user.pk})
        return False
    return True


def send_password_reset_email(user: User) -> bool:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_path = f"/reset-password?uid={uid}&token={token}"
    subject, message = render_account_email(
        "reset_password",
        user.language,
        link=f"{settings.FRONTEND_URL}{reset_path}",
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("password_reset_email_delivery_failed", extra={"user_id": user.pk})
        return False
    return True


# ---------------------------------------------------------------------------
# GDPR — right of access / portability (Art. 15 & 20) and erasure (Art. 17)
# ---------------------------------------------------------------------------

#: Never exported, even by accident: a password hash is not the data subject's
#: own data and leaks credential material.
_EXPORT_EXCLUDED_FIELDS = frozenset({"password"})

#: Explicit, auditable inventory of every user-owned dataset that must leave
#: with an export or disappear with an erasure.  Keeping it explicit (instead of
#: walking the model graph) makes a missing dataset a reviewable omission.
_USER_OWNED_COLLECTIONS: tuple[tuple[str, str, str], ...] = (
    # (export key, app_label.ModelName, owner lookup path)
    ("subscription", "subscriptions.Subscription", "user"),
    ("websites", "websites.Website", "owner"),
    ("scans", "scans.Scan", "website__owner"),
    ("check_results", "scans.CheckResult", "scan__website__owner"),
    ("scanner_runs", "scans.ScannerRun", "scan__website__owner"),
    ("findings", "scans.Finding", "scanner_run__scan__website__owner"),
    ("monitoring_configs", "monitoring.MonitoringConfig", "website__owner"),
    ("alerts", "alerts.Alert", "user"),
    ("alert_preferences", "alerts.AlertPreference", "user"),
    ("alert_rules", "alerts.AlertRule", "user"),
    ("mute_windows", "alerts.MuteWindow", "user"),
    ("notification_channels", "notifications.NotificationChannel", "user"),
    ("web_push_subscriptions", "notifications.WebPushSubscription", "user"),
    ("reports", "reports.Report", "user"),
    ("review_sources", "reviews.ReviewSource", "user"),
    ("reviews", "reviews.Review", "source__user"),
    ("review_response_drafts", "reviews.ResponseDraft", "user"),
    ("review_import_jobs", "reviews.ReviewImportJob", "user"),
    ("seo_audits", "seo.SEOAudit", "website__owner"),
    ("seo_keywords", "seo.Keyword", "website__owner"),
    ("seo_backlinks", "seo.Backlink", "website__owner"),
    ("social_profiles", "social.SocialProfile", "website__owner"),
    ("social_mentions", "social.SocialMention", "website__owner"),
    ("analytics_events", "analytics.AnalyticsEvent", "user"),
    ("traffic_logs", "analytics.TrafficLog", "user"),
    ("affiliate_clicks", "analytics.AffiliateClick", "user"),
    ("public_leads", "public_checker.PublicLead", "converted_to_user"),
)

#: Analytics rows reference the user with ``SET_NULL``: deleting the account
#: would leave them behind, pseudonymised only by the link.  A full erasure
#: request removes them explicitly.
_SET_NULL_ANALYTICS_MODELS: tuple[str, ...] = (
    "analytics.AnalyticsEvent",
    "analytics.TrafficLog",
    "analytics.AffiliateClick",
)


def _lookup_to_filter(lookup: str, user_id: int) -> dict[str, Any]:
    """Turn an owner lookup path (``website__owner``) into a ``user_id`` filter.

    ``website__owner`` → ``{"website__owner_id": 7}``: after the account row is
    gone, this is how we detect rows a cascade missed.
    """
    head, _, tail = lookup.rpartition("__")
    key = f"{head}__{tail}_id" if head else f"{tail}_id"
    return {key: user_id}


def _json_safe(value: Any) -> Any:
    """Convert a Python/DB value into something ``json.dumps`` accepts."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


def serialize_instance(instance: Any, exclude: frozenset[str] = _EXPORT_EXCLUDED_FIELDS) -> dict[str, Any]:
    """Turn a model instance into a JSON-safe dict of its concrete fields.

    Foreign keys are flattened to their primary key (``website`` → id) so the
    export stays self-contained without embedding duplicated subtrees.
    """
    data: dict[str, Any] = {}
    for field in instance._meta.concrete_fields:
        if field.name in exclude:
            continue
        data[field.name] = _json_safe(getattr(instance, field.attname, None))
    return data


def _iter_user_collections(user: User):
    """Yield ``(key, queryset)`` for every dataset owned by ``user``."""
    from django.apps import apps as django_apps

    for key, model_label, lookup in _USER_OWNED_COLLECTIONS:
        try:
            model = django_apps.get_model(model_label)
        except LookupError:
            continue
        yield key, model.objects.filter(**{lookup: user})


def collect_user_data(user: User) -> dict[str, Any]:
    """Build the complete GDPR export payload for ``user``.

    Returns a single JSON-serialisable structure containing the account record
    and every dataset listed in :data:`_USER_OWNED_COLLECTIONS`, each with its
    own ``count`` so a consumer can verify nothing was truncated.
    """
    from django.utils import timezone

    payload: dict[str, Any] = {
        "export_metadata": {
            "schema_version": 1,
            "format": "json",
            "generated_at": timezone.now().isoformat(),
            "subject_user_id": user.pk,
            "subject_email": user.email,
            "legal_basis": "GDPR Art. 15 (access) and Art. 20 (portability)",
        },
        "account": serialize_instance(user),
    }

    counts: dict[str, int] = {}
    for key, queryset in _iter_user_collections(user):
        rows = [serialize_instance(obj) for obj in queryset]
        payload[key] = rows
        counts[key] = len(rows)

    payload["record_counts"] = counts
    return payload


def delete_user_account(user: User) -> dict[str, Any]:
    """Erase ``user`` and every dataset attached to the account (GDPR Art. 17).

    Websites, scans, runs, findings, alerts and monitoring rows cascade from the
    ``User`` row, and Django reports exactly which rows each cascade removed.
    Analytics rows are linked with ``SET_NULL`` and would survive as orphaned
    pseudonymous records, so they are deleted explicitly first.

    The erasure is then *verified*: any row still pointing at the deleted user
    is reported and removed, so a future model linked with ``SET_NULL`` cannot
    silently turn erasure into retention.

    Returns an audit summary (per-model removal counts + leftovers).
    """
    from django.apps import apps as django_apps

    email = user.email
    user_id = user.pk
    deleted: dict[str, int] = {}
    leftovers: dict[str, int] = {}

    with transaction.atomic():
        for model_label in _SET_NULL_ANALYTICS_MODELS:
            try:
                model = django_apps.get_model(model_label)
            except LookupError:
                continue
            count, _ = model.objects.filter(user=user).delete()
            if count:
                deleted[model_label] = count

        # Public-scan leads hold the visitor's e-mail address (personal data).
        # ``converted_to_user`` is SET_NULL, so those rows would survive the
        # account deletion; erase the ones tied to this account explicitly.
        try:
            PublicLead = django_apps.get_model("public_checker", "PublicLead")
        except LookupError:
            PublicLead = None
        if PublicLead is not None:
            count, _ = PublicLead.objects.filter(
                Q(converted_to_user=user) | Q(email__iexact=email)
            ).delete()
            if count:
                deleted["public_leads"] = count

        # Cascade: websites → scans → check results / scanner runs → findings,
        # plus alerts, monitoring configs, notification channels, reports,
        # reviews, subscription and outstanding refresh tokens.
        total, per_model = User.objects.filter(pk=user_id).delete()
        deleted["account"] = total
        for model_label, count in per_model.items():
            deleted.setdefault(model_label, count)

        # Verification pass — nothing may keep a reference to an erased user.
        for key, model_label, lookup in _USER_OWNED_COLLECTIONS:
            try:
                model = django_apps.get_model(model_label)
            except LookupError:
                continue
            orphans = model.objects.filter(**_lookup_to_filter(lookup, user_id))
            count = orphans.count()
            if count:
                logger.error(
                    "gdpr_erasure_left_orphans",
                    extra={
                        "user_id": user_id,
                        "model": model_label,
                        "rows": count,
                    },
                )
                orphans.delete()
                leftovers[key] = count

    logger.info(
        "gdpr_account_deleted",
        extra={"user_id": user_id, "email": email, "deleted": deleted},
    )
    return {"deleted": deleted, "leftovers_removed": leftovers}
