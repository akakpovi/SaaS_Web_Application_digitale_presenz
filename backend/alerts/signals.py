import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from alerts.models import AlertPreference

logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_alert_preferences(sender, instance, created: bool, **kwargs) -> None:
    """Auto-create AlertPreference when a User is created."""
    if not created:
        return
    _, was_created = AlertPreference.objects.get_or_create(user=instance)
    if was_created:
        logger.info("AlertPreference created for user %s", instance.email)
