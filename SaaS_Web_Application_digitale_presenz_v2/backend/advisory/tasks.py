"""Celery entry point for AI recommendation generation.

The scan pipeline only enqueues this task.  Every failure path is contained
here: a provider outage, a malformed model answer or a broker problem must
never turn an otherwise successful website scan into a failed scan.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)

_DEFAULT_RETRY_COUNTDOWN = 120


@shared_task(
    bind=True,
    name="advisory.tasks.generate_scan_recommendations_task",
    max_retries=3,
    default_retry_delay=_DEFAULT_RETRY_COUNTDOWN,
    # The client may try two models with its own bounded HTTP retries.  Keep
    # enough headroom for the whole failover chain before Celery kills it.
    time_limit=600,
    soft_time_limit=570,
)
def generate_scan_recommendations_task(self, scan_id: int) -> dict:
    """Generate recommendations for a completed authenticated scan.

    The feature flag is checked both by the dispatcher and here, so an old
    queued message cannot generate billable AI traffic after a kill switch.
    """
    if not getattr(settings, "AI_ADVISOR_ENABLED", False):
        logger.info("AI advisor disabled; skipping scan %s", scan_id)
        return {"scan_id": scan_id, "status": "disabled"}

    from scans.models import Scan

    scan = Scan.objects.filter(pk=scan_id).only(
        "id", "status", "is_guest"
    ).first()
    if scan is None:
        return {"scan_id": scan_id, "status": "not_found"}
    if scan.is_guest:
        return {"scan_id": scan_id, "status": "skipped_guest"}
    if scan.status != Scan.Status.COMPLETED:
        return {
            "scan_id": scan_id,
            "status": "skipped_not_completed",
            "scan_status": scan.status,
        }

    from advisory.services.advisor import generate_recommendations_for_scan

    retries = int(getattr(self.request, "retries", 0) or 0)
    try:
        result = generate_recommendations_for_scan(
            scan_id,
            retry_failed=retries > 0,
        )
    except Exception as exc:
        # The run record is the source of truth for the failure.  Do not leak
        # provider bodies or prompt data into the Celery result or logs.
        logger.exception(
            "AI advisor task failed scan=%s error=%s",
            scan_id,
            exc.__class__.__name__,
        )
        return {
            "scan_id": scan_id,
            "status": "error",
            "error": exc.__class__.__name__,
        }

    payload = {
        "scan_id": scan_id,
        "status": result.run.status,
        "run_id": str(result.run.id),
        "used_fallback": result.used_fallback,
        "model_used": result.run.model_used,
        "recommendations": len(result.recommendations),
        "error_code": result.error_code,
    }

    if result.should_retry:
        max_countdown = int(
            getattr(settings, "AI_ADVISOR_RETRY_MAX_SECONDS", 900)
        )
        countdown = min(
            max(result.retry_after_seconds or _DEFAULT_RETRY_COUNTDOWN, 30),
            max_countdown,
        )
        if retries < self.max_retries:
            logger.warning(
                "AI advisor retry scheduled scan=%s code=%s in %ss "
                "(attempt %s/%s)",
                scan_id,
                result.error_code or "unknown",
                countdown,
                retries + 1,
                self.max_retries,
            )
            raise self.retry(countdown=countdown)
        payload["status"] = "failed_quota_exhausted"

    logger.info(
        "AI advisor finished scan=%s status=%s fallback=%s model=%s",
        scan_id,
        payload["status"],
        result.used_fallback,
        result.run.model_used or "-",
    )
    return payload
