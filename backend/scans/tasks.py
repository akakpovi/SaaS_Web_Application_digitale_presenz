import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60, name="scans.tasks.run_authenticated_scan")
def run_authenticated_scan(self, scan_id: int):
    from scans.models import Scan
    try:
        scan = Scan.objects.get(id=scan_id)
        scan.status = Scan.Status.COMPLETED
        scan.completed_at = timezone.now()
        scan.save(update_fields=["status", "completed_at"])
        logger.info("✅ Scan authentifié %s terminé avec succès.", scan_id)
    except Exception as e:
        logger.error("❌ Erreur scan authentifié %s: %s", scan_id, e)

@shared_task(name="scans.tasks.purge_guest_data")
def purge_guest_data():
    from scans.models import Scan
    from websites.models import Website
    cutoff = timezone.now() - timedelta(hours=24)
    scans_deleted, _ = Scan.objects.filter(is_guest=True, created_at__lt=cutoff).delete()
    websites_deleted, _ = Website.objects.filter(is_guest=True, created_at__lt=cutoff).delete()
    logger.info("🧹 Purge nocturne : %s scans et %s sites guest supprimés.", scans_deleted, websites_deleted)
    return {"scans_deleted": scans_deleted, "websites_deleted": websites_deleted}
