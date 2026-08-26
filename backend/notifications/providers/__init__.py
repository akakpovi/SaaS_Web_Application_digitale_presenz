from notifications.models import NotificationChannel
from .base import NotificationProvider
from .email import EmailNotificationProvider
from .slack import SlackNotificationProvider

_PROVIDER_MAP: dict[str, type[NotificationProvider]] = {
    NotificationChannel.ChannelType.EMAIL: EmailNotificationProvider,
    NotificationChannel.ChannelType.SLACK: SlackNotificationProvider,
}


def get_provider(channel: NotificationChannel) -> NotificationProvider | None:
    """Return the appropriate provider instance for a channel."""
    cls = _PROVIDER_MAP.get(channel.channel_type)
    return cls(config=channel.config) if cls else None


__all__ = [
    "NotificationProvider",
    "EmailNotificationProvider",
    "SlackNotificationProvider",
    "get_provider",
]
