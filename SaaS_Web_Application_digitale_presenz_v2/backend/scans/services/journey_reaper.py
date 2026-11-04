"""Periodic maintenance for progressive scan journeys (Lot E).

A journey can stop progressing in three ways the normal callbacks cannot
repair: the user never confirms stage 2, a worker dies after its child scan
became terminal, or the child scan disappears.  This module closes those
journeys without touching classic scans, the orchestration service or the
existing scan reaper.

Every pass is idempotent:

* expiry uses a conditional ``UPDATE ... WHERE state = 'awaiting_confirmation'``;
* reconciliation delegates to :meth:`JourneyService.on_stage_completed`, which
  re-reads the journey under a row lock;
* orphan cleanup locks the journey and re-checks for an active child scan
  before writing ``failed``.

The reaper never deletes a row and never changes a scan.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from scans.models import JourneyState, Scan, ScanJourney
from scans.services.journey_coverage import check_journey_coverage
from scans.services.journey_service import JourneyService

logger = logging.getLogger(__name__)

#: Bound every pass so a large backlog cannot turn one tick into a long job.
_MAX_JOURNEYS_PER_PASS = 500

_TERMINAL_SCAN_STATUSES = (
    Scan.Status.COMPLETED,
    Scan.Status.PARTIAL,
    Scan.Status.FAILED,
    Scan.Status.CANCELLED,
)


def _positive_int_setting(name: str, default: int) -> int:
    """Read a positive integer setting, falling back on bad configuration."""
    try:
        return max(1, int(getattr(settings, name, default)))
    except (TypeError, ValueError):
        return default


def reap_expired_journeys(now: Any | None = None) -> int:
    """Expire journeys whose confirmation window has elapsed.

    Only ``awaiting_confirmation`` journeys with ``expires_at <= now`` are
    touched.  A user-confirmed (``running``) or terminal journey is never
    affected.  The deadline is overwritten with the reaping instant so the
    row records when it expired; the original deadline remains in the log.

    Returns the number of journeys actually transitioned.
    """
    now = now or timezone.now()
    candidate_ids = list(
        ScanJourney.objects.filter(
            state=JourneyState.AWAITING_CONFIRMATION,
            expires_at__lte=now,
        )
        .order_by("expires_at")
        .values_list("id", flat=True)[:_MAX_JOURNEYS_PER_PASS]
    )

    expired = 0
    for journey_id in candidate_ids:
        updated = ScanJourney.objects.filter(
            pk=journey_id,
            state=JourneyState.AWAITING_CONFIRMATION,
            expires_at__lte=now,
        ).update(
            state=JourneyState.EXPIRED,
            expires_at=now,
            updated_at=now,
        )
        if not updated:
            # A concurrent advance/cancel won the race; leave it alone.
            continue
        expired += 1
        logger.info(
            "journey_reaped journey_id=%s previous_state=%s new_state=%s "
            "reason=confirmation_window_elapsed expires_at=%s",
            journey_id,
            JourneyState.AWAITING_CONFIRMATION,
            JourneyState.EXPIRED,
            now.isoformat(),
        )

    if expired:
        logger.info("journey_reaper_expired count=%d", expired)
    return expired


def reconcile_stale_journeys() -> int:
    """Replay the stage callback for journeys stuck in ``running``.

    A running journey whose current child scan is already terminal means the
    Celery callback never arrived.  Calling the normal service method keeps
    the transition rules (awaiting confirmation, completed, partial, failed)
    in one place.  A missing child scan is an anomaly: it is logged and left
    for manual inspection, never guessed.
    """
    journeys = list(
        ScanJourney.objects.filter(state=JourneyState.RUNNING)
        .select_related("website")
        .order_by("updated_at")[:_MAX_JOURNEYS_PER_PASS]
    )

    reconciled = 0
    for journey in journeys:
        current_scan = (
            Scan.objects.filter(
                journey=journey,
                journey_stage=journey.current_stage,
            )
            .only("id", "status", "journey_stage")
            .first()
        )
        if current_scan is None:
            logger.warning(
                "journey_reaper_no_child journey_id=%s stage=%s state=%s "
                "action=manual_inspection",
                journey.pk,
                journey.current_stage,
                journey.state,
            )
            continue
        if current_scan.status not in _TERMINAL_SCAN_STATUSES:
            # The worker may simply be slow; the scan reaper owns this case.
            continue

        previous_state = journey.state
        try:
            updated = JourneyService.on_stage_completed(current_scan.pk)
        except Exception:
            logger.exception(
                "journey_reaper_reconcile_failed journey_id=%s scan_id=%s "
                "scan_status=%s",
                journey.pk,
                current_scan.pk,
                current_scan.status,
            )
            continue
        if updated is None:
            continue

        reconciled += 1
        logger.info(
            "journey_reconciled journey_id=%s scan_id=%s scan_status=%s "
            "previous_state=%s new_state=%s",
            journey.pk,
            current_scan.pk,
            current_scan.status,
            previous_state,
            updated.state,
        )

    if reconciled:
        logger.info("journey_reaper_reconciled count=%d", reconciled)
    return reconciled


def reap_orphan_journeys(now: Any | None = None) -> int:
    """Fail old running journeys that no longer have an active child scan.

    The TTL is the same as the confirmation window.  A journey younger than
    the TTL, or one whose current child scan is still pending/queued/running,
    is left alone: the worker may still be working or the scan reaper will
    close the child on a later tick.
    """
    now = now or timezone.now()
    ttl_hours = JourneyService.journey_ttl_hours()
    cutoff = now - timedelta(hours=ttl_hours)

    candidate_ids = list(
        ScanJourney.objects.filter(
            state=JourneyState.RUNNING,
            created_at__lte=cutoff,
        )
        .order_by("created_at")
        .values_list("id", flat=True)[:_MAX_JOURNEYS_PER_PASS]
    )

    reaped = 0
    for journey_id in candidate_ids:
        with transaction.atomic():
            journey = (
                ScanJourney.objects.select_for_update()
                .filter(pk=journey_id, state=JourneyState.RUNNING)
                .only("pk", "current_stage", "created_at")
                .first()
            )
            if journey is None:
                continue

            has_active_scan = (
                Scan.objects.filter(
                    journey_id=journey.pk,
                    journey_stage=journey.current_stage,
                )
                .exclude(status__in=_TERMINAL_SCAN_STATUSES)
                .exists()
            )
            if has_active_scan:
                continue

            journey.state = JourneyState.FAILED
            journey.expires_at = None
            journey.save(update_fields=["state", "expires_at", "updated_at"])

        reaped += 1
        logger.warning(
            "journey_reaped journey_id=%s previous_state=%s new_state=%s "
            "reason=orphaned_no_active_scan created_at=%s ttl_hours=%s",
            journey_id,
            JourneyState.RUNNING,
            JourneyState.FAILED,
            journey.created_at.isoformat(),
            ttl_hours,
        )

    if reaped:
        logger.info("journey_reaper_orphans count=%d", reaped)
    return reaped


def journey_gauges() -> dict[str, int]:
    """Return the current active/awaiting counts for the metrics gauges."""
    counts = ScanJourney.objects.aggregate(
        active=Count(
            "id",
            filter=Q(
                state__in=[
                    JourneyState.RUNNING,
                    JourneyState.AWAITING_CONFIRMATION,
                ]
            ),
        ),
        awaiting=Count(
            "id",
            filter=Q(state=JourneyState.AWAITING_CONFIRMATION),
        ),
    )
    return {
        "active": int(counts["active"] or 0),
        "awaiting": int(counts["awaiting"] or 0),
    }


def reap_journeys() -> dict[str, Any]:
    """Run every journey maintenance pass and record its metrics.

    Order matters: expired, reconciled and orphaned journeys are closed
    *before* the coverage check, so an issue repaired during this tick does
    not raise an alert.  The reaper-inactive check reads the previous tick
    and therefore still sees a real gap when the reaper resumes late.
    """
    expired = reap_expired_journeys()
    reconciled = reconcile_stale_journeys()
    orphans = reap_orphan_journeys()

    coverage = check_journey_coverage()
    gauges = journey_gauges()

    metrics: dict[str, Any] = {
        "expired": expired,
        "reconciled": reconciled,
        "orphans": orphans,
        "total": expired + reconciled + orphans,
        "active": gauges["active"],
        "awaiting": gauges["awaiting"],
        "coverage_alerts": coverage["alerts_created"],
        "reaper_inactive": coverage["reaper_inactive"],
    }

    try:
        from core.reaper_metrics import record_journey_reaper_tick

        record_journey_reaper_tick(
            expired=expired,
            reconciled=reconciled,
            orphans=orphans,
            active=gauges["active"],
            awaiting=gauges["awaiting"],
        )
    except Exception:
        # A cache outage must never roll back or block the database sweep.
        logger.warning("journey_reaper_metrics_failed", exc_info=True)

    logger.info("journey_reaper_tick %s", metrics)
    return metrics
