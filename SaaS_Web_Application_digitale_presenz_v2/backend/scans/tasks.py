"""Celery tasks for the Scan Engine.

Primary task: ``run_authenticated_scan`` — the real orchestrator entry point.

All other scan-related background work lives here too (purge, cancel, etc.).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="scans.tasks.run_authenticated_scan",
    # Per-task time limits — override the global 600s for health scans (should be faster)
    time_limit=600,
    soft_time_limit=570,
)
def run_authenticated_scan(self, scan_id: int) -> dict:
    """Execute a full scan via the ScanOrchestrator.

    This is the real implementation.  The previous stub that just set
    status=COMPLETED without running any scanners has been replaced.

    The task is idempotent: if the scan is already COMPLETED or FAILED,
    the orchestrator exits immediately.
    """
    from scans.services.orchestrator import ScanOrchestrator
    from scans.models import Scan

    logger.info("Starting scan task for scan_id=%d", scan_id)
    try:
        orchestrator = ScanOrchestrator(scan_id=scan_id)
        orchestrator.run()
        logger.info("Scan task completed for scan_id=%d", scan_id)
        return {"scan_id": scan_id, "status": "done"}
    except Exception as exc:
        logger.exception("Scan task failed for scan_id=%d: %s", scan_id, exc)
        # Mark scan as failed if the orchestrator itself crashed.
        try:
            scan = Scan.objects.get(pk=scan_id)
            if scan.status not in (Scan.Status.COMPLETED, Scan.Status.FAILED, Scan.Status.CANCELLED):
                scan.transition_to(Scan.Status.FAILED, failure_message=str(exc)[:500])
        except Exception:
            pass
        raise


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="scans.tasks.run_health_scan",
    time_limit=300,
    soft_time_limit=280,
)
def run_health_scan(self, scan_id: int) -> dict:
    """Convenience alias: run a HEALTH-type scan."""
    return run_authenticated_scan.apply(args=[scan_id]).get()


@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=60,
    name="scans.tasks.run_security_scan",
    time_limit=600,
    soft_time_limit=570,
)
def run_security_scan(self, scan_id: int) -> dict:
    """Convenience alias: run a SECURITY-type scan (external tools)."""
    return run_authenticated_scan.apply(args=[scan_id]).get()


@shared_task(name="scans.tasks.cancel_scan")
def cancel_scan(scan_id: int) -> dict:
    """Attempt to cancel a running or queued scan."""
    from scans.models import Scan

    try:
        scan = Scan.objects.get(pk=scan_id)
        if scan.is_active:
            scan.transition_to(Scan.Status.CANCELLED)
            logger.info("Scan %d cancelled", scan_id)
            return {"scan_id": scan_id, "cancelled": True}
        return {"scan_id": scan_id, "cancelled": False, "reason": scan.status}
    except Scan.DoesNotExist:
        return {"scan_id": scan_id, "cancelled": False, "reason": "not_found"}


@shared_task(name="scans.tasks.purge_guest_data")
def purge_guest_data() -> dict:
    """Nightly purge of guest scan data older than 24 hours."""
    from scans.models import Scan
    from websites.models import Website

    cutoff = timezone.now() - timedelta(hours=24)
    scans_deleted, _ = Scan.objects.filter(is_guest=True, created_at__lt=cutoff).delete()
    websites_deleted, _ = Website.objects.filter(is_guest=True, created_at__lt=cutoff).delete()
    logger.info(
        "Nightly purge: %d scans and %d guest websites deleted",
        scans_deleted,
        websites_deleted,
    )
    return {"scans_deleted": scans_deleted, "websites_deleted": websites_deleted}
