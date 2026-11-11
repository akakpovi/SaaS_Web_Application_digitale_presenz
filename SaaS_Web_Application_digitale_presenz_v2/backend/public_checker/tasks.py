"""Celery tasks for the public website checker."""

from __future__ import annotations

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="public_checker.run_public_scan",
    time_limit=300,
    soft_time_limit=280,
)
def run_public_scan(self, scan_id: int) -> dict:
    """Execute a public health scan via the ScanOrchestrator.

    The scan record is created synchronously by the view before dispatching this task.
    This task runs the scan pipeline and updates the scan in place.
    """
    from scans.services.orchestrator import ScanOrchestrator
    from scans.models import Scan

    logger.info("Starting public scan task for scan_id=%d", scan_id)
    try:
        orchestrator = ScanOrchestrator(scan_id=scan_id)
        orchestrator.run()
        logger.info("Public scan task completed for scan_id=%d", scan_id)
        return {"scan_id": scan_id, "status": "done"}
    except Exception as exc:
        logger.exception("Public scan task failed for scan_id=%d: %s", scan_id, exc)
        try:
            scan = Scan.objects.get(pk=scan_id)
            if scan.status not in (
                Scan.Status.COMPLETED,
                Scan.Status.PARTIAL,
                Scan.Status.FAILED,
                Scan.Status.CANCELLED,
            ):
                scan.transition_to(Scan.Status.FAILED, failure_message=str(exc)[:500])
        except Exception:
            pass
        raise
