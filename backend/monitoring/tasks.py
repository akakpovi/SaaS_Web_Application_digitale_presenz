import logging
import random
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from monitoring.models import INTERVAL_MAP, MonitoringConfig

logger = logging.getLogger(__name__)


@shared_task(name="monitoring.tasks.run_due_monitors")
def run_due_monitors() -> dict:
    """
    Periodic task (every 5 min):
    1. Find MonitoringConfig with next_scan_at <= now
    2. Skip muted websites
    3. Queue a new Scan
    4. Schedule next_scan_at with jitter
    """
    from alerts.models import MuteWindow
    from scans.models import Scan
    from scans.tasks import run_authenticated_scan

    now = timezone.now()
    configs = MonitoringConfig.objects.filter(
        enabled=True,
        next_scan_at__lte=now,
    ).select_related("website", "website__owner")

    queued, skipped = 0, 0

    for config in configs:
        website = config.website

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
            config.next_scan_at = now + timedelta(hours=1)
            config.save(update_fields=["next_scan_at", "updated_at"])
            skipped += 1
            logger.info("Skipped muted website %s", website.domain)
            continue

        # Create and queue scan
        scan = Scan.objects.create(
            website=website,
            trigger=Scan.Trigger.MONITORING,
            status=Scan.Status.QUEUED,
        )
        run_authenticated_scan.delay(scan.id)

        # Schedule next with jitter
        interval_td = INTERVAL_MAP.get(config.interval, timedelta(hours=24))
        jitter = timedelta(minutes=random.randint(0, 5))
        config.last_scan_at = now
        config.next_scan_at = now + interval_td + jitter
        config.save(update_fields=["last_scan_at", "next_scan_at", "updated_at"])
        queued += 1

        logger.info(
            "Queued monitoring scan %s for %s (next: %s)",
            scan.id, website.domain, config.next_scan_at,
        )

    logger.info("run_due_monitors: queued=%d skipped=%d", queued, skipped)
    return {"queued": queued, "skipped": skipped}
