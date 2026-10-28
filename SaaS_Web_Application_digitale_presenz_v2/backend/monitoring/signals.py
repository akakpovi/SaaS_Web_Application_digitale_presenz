import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from monitoring.models import MonitoringConfig
from websites.models import Website

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Website)
def create_monitoring_config(sender, instance, created: bool, **kwargs) -> None:
    """Auto-create MonitoringConfig when a Website is created.

    The config starts disabled with no schedule: continuous monitoring is
    opt-in, offered to the owner after the first scan.  Enabling it (through
    the API) is what sets ``next_scan_at``.
    """
    if not created:
        return
    config, was_created = MonitoringConfig.objects.get_or_create(
        website=instance,
        defaults={
            "enabled": False,
            "interval": MonitoringConfig.Interval.TWENTY_FOUR,
        },
    )
    if was_created:
        logger.info("MonitoringConfig created for website %s", instance.domain)
