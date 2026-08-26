import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from monitoring.models import MonitoringConfig
from websites.models import Website

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Website)
def create_monitoring_config(sender, instance, created: bool, **kwargs) -> None:
    """Auto-create MonitoringConfig when a Website is created."""
    if not created:
        return
    config, was_created = MonitoringConfig.objects.get_or_create(
        website=instance,
        defaults={
            "enabled": True,
            "interval": MonitoringConfig.Interval.TWENTY_FOUR,
            "next_scan_at": timezone.now(),
        },
    )
    if was_created:
        logger.info("MonitoringConfig created for website %s", instance.domain)
