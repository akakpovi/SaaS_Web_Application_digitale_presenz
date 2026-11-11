"""Alert dispatch to notification channels."""

import logging
from notifications.models import NotificationChannel
from notifications.providers import get_provider

logger = logging.getLogger(__name__)


def dispatch_alert(alert) -> None:
    """Dispatch alert to all configured channels for the user."""
    user = alert.user
    channels = NotificationChannel.objects.filter(user=user, enabled=True)

    sent_to = []
    for channel in channels:
        if not channel.matches(alert.severity, alert.alert_type):
            continue

        try:
            provider = get_provider(channel)
            if provider and provider.send(alert, user):
                sent_to.append(channel.channel_type)
                logger.info(
                    f"Alert {alert.id} dispatched via {channel.channel_type}",
                    extra={"alert_id": str(alert.id), "channel_id": channel.id},
                )
            else:
                logger.warning(
                    f"Failed to dispatch alert via {channel.channel_type}",
                    extra={"alert_id": str(alert.id)},
                )
        except Exception:
            logger.exception(
                f"Exception dispatching alert via {channel.channel_type}",
                extra={"alert_id": str(alert.id)},
            )

    if sent_to:
        alert.notification_channels_sent = sent_to
        alert.save(update_fields=["notification_channels_sent"])
