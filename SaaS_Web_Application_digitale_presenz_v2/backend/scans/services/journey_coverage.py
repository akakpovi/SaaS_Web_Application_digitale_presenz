"""Coverage alerts for progressive scan journeys (Lot E).

The existing :func:`alerts.tasks.report_scan_issue` is keyed on a ``Scan``:
a journey waiting for confirmation has no active scan, and a global
"reaper inactive" condition has no website at all.  This module therefore
creates the same ``scan_failed`` coverage alert directly, reusing the
existing ``Alert`` table, ``AlertPreference`` switch, mute windows and
notification dispatcher.

Only journeys are inspected here.  Classic scan alerts keep going through
``report_scan_issue`` unchanged.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

from scans.models import JourneyState, ScanJourney

logger = logging.getLogger(__name__)

#: Issues are stored in ``Alert.metadata`` and used for de-duplication.
ISSUE_STUCK_AWAITING = "journey_stuck_awaiting"
ISSUE_STUCK_RUNNING = "journey_stuck_running"
ISSUE_ACCUMULATION = "journey_accumulation"
ISSUE_REAPER_INACTIVE = "journey_reaper_inactive"

_MAX_ALERTS_PER_CHECK = 200


def _setting_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(getattr(settings, name, default)))
    except (TypeError, ValueError):
        return default


def _awaiting_threshold_hours() -> int:
    """Half the confirmation TTL, as specified for the warning threshold."""
    ttl = _setting_int("SCAN_JOURNEY_TTL_HOURS", 24)
    return _setting_int(
        "SCAN_JOURNEY_STUCK_AWAITING_HOURS",
        max(1, ttl // 2),
    )


def _parse_tick(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _has_firing_alert(website, issue: str, journey_id: int | None) -> bool:
    """True when this issue already has a firing journey alert.

    ``journey_id=None`` de-duplicates at website level (accumulation).
    """
    from alerts.models import Alert

    alerts = Alert.objects.filter(
        website=website,
        alert_type=Alert.AlertType.SCAN_FAILED,
        status=Alert.Status.FIRING,
    ).values_list("metadata", flat=True)
    for metadata in alerts:
        metadata = metadata or {}
        if metadata.get("kind") != "journeys":
            continue
        if metadata.get("issue") != issue:
            continue
        if journey_id is not None and metadata.get("journey_id") != journey_id:
            continue
        return True
    return False


def _create_alert(
    journey: ScanJourney,
    *,
    issue: str,
    severity: str,
    title: str,
    message: str,
    extra: dict[str, Any] | None = None,
    dedupe_by_journey: bool = True,
) -> bool:
    """Create and dispatch one journey coverage alert, or skip it.

    Skips when the owner disabled ``scan_failed`` alerts, when a mute window
    covers the site, or when the same issue is already firing.  Never raises
    for a missing owner: a guest/legacy website is logged and ignored.
    """
    from alerts.models import Alert, AlertPreference, MuteWindow
    from core.escalation import should_create_alert
    from notifications.dispatcher import dispatch_alert

    website = journey.website
    owner = website.owner
    if owner is None:
        logger.warning(
            "journey_coverage_alert_no_owner journey_id=%s issue=%s",
            journey.pk,
            issue,
        )
        return False

    preferences, _ = AlertPreference.objects.get_or_create(user=owner)
    if not should_create_alert(Alert.AlertType.SCAN_FAILED, preferences):
        return False

    now = timezone.now()
    active_mutes = MuteWindow.objects.filter(
        user=owner,
        is_active=True,
        start_at__lte=now,
        end_at__gte=now,
    )
    if (
        active_mutes.filter(websites__isnull=True).exists()
        or active_mutes.filter(websites=website).exists()
    ):
        return False

    journey_key = journey.pk if dedupe_by_journey else None
    if _has_firing_alert(website, issue, journey_key):
        return False

    metadata: dict[str, Any] = {
        "kind": "journeys",
        "issue": issue,
        "journey_id": journey.pk,
        "state": journey.state,
        "stage": journey.current_stage,
    }
    if extra:
        metadata.update(extra)

    alert = Alert.objects.create(
        user=owner,
        website=website,
        scan=None,
        alert_type=Alert.AlertType.SCAN_FAILED,
        severity=severity,
        title=title,
        message=message,
        metadata=metadata,
    )
    dispatch_alert(alert)
    logger.warning(
        "journey_coverage_alert issue=%s journey_id=%s website_id=%s "
        "severity=%s alert_id=%s",
        issue,
        journey.pk,
        website.pk,
        severity,
        alert.pk,
    )
    return True


def _alert_stuck_awaiting(now: datetime) -> int:
    from alerts.models import Alert

    hours = _awaiting_threshold_hours()
    cutoff = now - timedelta(hours=hours)
    journeys = (
        ScanJourney.objects.filter(
            state=JourneyState.AWAITING_CONFIRMATION,
            updated_at__lte=cutoff,
        )
        .select_related("website", "website__owner")
        .order_by("updated_at")[:_MAX_ALERTS_PER_CHECK]
    )

    created = 0
    for journey in journeys:
        if _create_alert(
            journey,
            issue=ISSUE_STUCK_AWAITING,
            severity=Alert.Severity.WARNING,
            title=(
                "Scan journey stuck awaiting confirmation for "
                f"{journey.website.domain}"
            ),
            message=(
                f"Journey {journey.pk} has been awaiting confirmation for "
                f"more than {hours} h. It will expire automatically; the "
                "site stays blocked for a new journey until then."
            ),
            extra={
                "hours": hours,
                "expires_at": (
                    journey.expires_at.isoformat()
                    if journey.expires_at
                    else None
                ),
            },
        ):
            created += 1
    return created


def _alert_stuck_running(now: datetime) -> int:
    from alerts.models import Alert

    minutes = _setting_int("SCAN_JOURNEY_STUCK_RUNNING_MINUTES", 60)
    cutoff = now - timedelta(minutes=minutes)
    journeys = (
        ScanJourney.objects.filter(
            state=JourneyState.RUNNING,
            updated_at__lte=cutoff,
        )
        .select_related("website", "website__owner")
        .order_by("updated_at")[:_MAX_ALERTS_PER_CHECK]
    )

    created = 0
    for journey in journeys:
        if _create_alert(
            journey,
            issue=ISSUE_STUCK_RUNNING,
            severity=Alert.Severity.WARNING,
            title=f"Scan journey stuck running for {journey.website.domain}",
            message=(
                f"Journey {journey.pk} has been running for more than "
                f"{minutes} min without progress. The reaper reconciles it "
                "when its child scan is terminal; inspect the worker if it "
                "stays running."
            ),
            extra={"minutes": minutes},
        ):
            created += 1
    return created


def _alert_accumulation(now: datetime) -> int:
    from alerts.models import Alert

    threshold = _setting_int(
        "SCAN_JOURNEY_ACCUMULATION_THRESHOLD",
        3,
        minimum=0,
    )
    rows = (
        ScanJourney.objects.filter(state=JourneyState.AWAITING_CONFIRMATION)
        .values("website_id")
        .annotate(total=Count("id"))
        .filter(total__gt=threshold)
        .order_by("-total")[:_MAX_ALERTS_PER_CHECK]
    )

    created = 0
    for row in rows:
        journey = (
            ScanJourney.objects.filter(
                website_id=row["website_id"],
                state=JourneyState.AWAITING_CONFIRMATION,
            )
            .select_related("website", "website__owner")
            .order_by("created_at")
            .first()
        )
        if journey is None:
            continue
        if _create_alert(
            journey,
            issue=ISSUE_ACCUMULATION,
            severity=Alert.Severity.WARNING,
            title=(
                "Multiple scan journeys awaiting confirmation for "
                f"{journey.website.domain}"
            ),
            message=(
                f"{row['total']} journeys are waiting on this website "
                f"(threshold {threshold}). The per-website active journey "
                "constraint should normally keep this at one."
            ),
            extra={"count": row["total"], "threshold": threshold},
            dedupe_by_journey=False,
        ):
            created += 1
    return created


def _check_reaper_inactive(now: datetime) -> bool:
    """Log CRITICAL when the previous journey tick is older than the limit.

    A global alert row cannot represent this condition: ``Alert`` requires a
    user and a website, while a dead beat has neither.  The condition is
    therefore a CRITICAL log plus the boolean returned to the task result and
    the metrics; an external monitor can watch ``journeys_last_tick``.
    """
    from core.reaper_metrics import JOURNEYS_LAST_TICK_KEY

    minutes = _setting_int("SCAN_JOURNEY_REAPER_INACTIVE_MINUTES", 15)
    try:
        last_tick = cache.get(JOURNEYS_LAST_TICK_KEY)
    except Exception:
        logger.warning("journey_reaper_tick_unreadable", exc_info=True)
        return False

    last_dt = _parse_tick(last_tick)
    if last_dt is None:
        # First run after a deploy/cache flush: nothing to compare yet.
        return False

    age_seconds = (now - last_dt).total_seconds()
    if age_seconds <= minutes * 60:
        return False

    logger.critical(
        "journey_reaper_inactive issue=%s last_tick=%s age_s=%d "
        "threshold_s=%d action=check_beat_worker",
        ISSUE_REAPER_INACTIVE,
        last_tick,
        int(age_seconds),
        minutes * 60,
    )
    return True


def check_journey_coverage(now: Any | None = None) -> dict[str, Any]:
    """Emit the journey coverage alerts and report what was created.

    Called by :func:`scans.services.journey_reaper.reap_journeys` after the
    repair passes, so a journey fixed during this tick does not alert.
    ``reaper_inactive`` is True when the previous tick is older than the
    configured threshold; it does not create an ``Alert`` row (no website).
    """
    now = now or timezone.now()
    created = 0
    created += _alert_stuck_awaiting(now)
    created += _alert_stuck_running(now)
    created += _alert_accumulation(now)
    inactive = _check_reaper_inactive(now)

    if created:
        logger.warning("journey_coverage_alerts_created count=%d", created)
    return {"alerts_created": created, "reaper_inactive": inactive}
