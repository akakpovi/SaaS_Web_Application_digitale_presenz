"""Notification signals.

The alert engine (``alerts.tasks.detect_alerts``) creates ``Alert`` rows and
hands them to ``notifications.dispatcher.dispatch_alert``, which only delivers
through *enabled* ``NotificationChannel`` rows.  A user with no channel was
therefore silently never notified — alerts piled up in the database and no
e-mail ever left the server.

Every user now gets one enabled e-mail channel pointing at their own address,
so alert e-mails work out of the box.  Users can still edit, disable or delete
it from the notifications API.
"""

import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def ensure_default_email_channel(user) -> bool:
    """Create the default e-mail channel for ``user`` if there is none.

    Idempotent, and never resurrects a channel the user has deliberately
    removed once *another* channel exists.  Returns True when a channel was
    created.
    """
    from notifications.models import NotificationChannel

    exists = NotificationChannel.objects.filter(
        user=user, channel_type=NotificationChannel.ChannelType.EMAIL
    ).exists()
    if exists:
        return False

    NotificationChannel.objects.create(
        user=user,
        channel_type=NotificationChannel.ChannelType.EMAIL,
        name="Email alerts",
        enabled=True,
        config={"email": user.email},
    )
    logger.info("Default e-mail alert channel created for user %s", user.email)
    return True


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_default_notification_channel(sender, instance, created: bool, **kwargs) -> None:
    """Provision the default e-mail channel when a User is created."""
    if not created:
        return
    try:
        ensure_default_email_channel(instance)
    except Exception:
        # Never let notification provisioning break registration.
        logger.exception(
            "Could not create the default e-mail channel for %s", instance.email
        )
