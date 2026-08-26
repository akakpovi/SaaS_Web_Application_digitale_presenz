import logging
from celery import shared_task
from django.db import transaction

from scans.models import Scan, CheckResult
from scans.services.scoring import recalculate_scan_health
from public_checker.tasks import PUBLIC_SCANNERS

logger = logging.getLogger(__name__)


@shared_task
def run_authenticated_scan(scan_id: int) -> None:
    """Run all scanners for an authenticated user's website."""
    try:
        scan = Scan.objects.select_related("website").get(pk=scan_id)
    except Scan.DoesNotExist:
        logger.error(f"Scan {scan_id} not found.")
        return

    if scan.status != Scan.Status.QUEUED:
        logger.warning(f"Scan {scan_id} is not in QUEUED state. Current: {scan.status}")
        return

    Scan.objects.filter(pk=scan_id).update(status=Scan.Status.RUNNING)
    domain = scan.website.domain

    for category, scanner in PUBLIC_SCANNERS.items():
        try:
            result = scanner.scan(domain)
            CheckResult.objects.update_or_create(
                scan_id=scan_id,
                category=category,
                defaults={
                    "status": result.status,
                    "score": result.score,
                    "summary": result.message,
                    "recommendation": result.recommendation,
                    "technical_details": {
                        **result.details,
                        "duration_ms": result.duration_ms,
                    },
                }
            )
        except Exception as e:
            logger.exception(f"Error running {category} scanner for scan {scan_id}")
            CheckResult.objects.update_or_create(
                scan_id=scan_id,
                category=category,
                defaults={
                    "status": "critical",
                    "score": 0,
                    "summary": "Scanner failed unexpectedly",
                    "technical_details": {"error": str(e)},
                }
            )

    with transaction.atomic():
        scan.refresh_from_db()
        recalculate_scan_health(scan)
        scan.status = Scan.Status.COMPLETED
        scan.save(update_fields=["status", "health_score", "health_status"])

    logger.info(f"Authenticated scan {scan_id} completed successfully.")

    from alerts.tasks import detect_alerts
    detect_alerts.delay(scan_id)
