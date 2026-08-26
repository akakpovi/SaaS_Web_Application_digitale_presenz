import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def dispatch_alert(alert) -> list[str]:
    """
    Send alert via all matching enabled notification channels.
    Respects: quiet hours, mute windows, severity/type filters.
    Returns list of channel types that succeeded.
    """
    from alerts.models import MuteWindow
    from notifications.models import NotificationChannel
    from notifications.providers import get_provider

    user = alert.user
    now = timezone.now()

    # Quiet hours
    try:
        prefs = user.alert_preferences
        if prefs.is_in_quiet_hours(now):
            logger.info("Alert %s suppressed — quiet hours for user %s", alert.id, user.email)
            return []
    except Exception:
        pass

    # Mute windows
    active_mutes = MuteWindow.objects.filter(
        user=user, is_active=True, start_at__lte=now, end_at__gte=now
    )
    if (
        active_mutes.filter(websites__isnull=True).exists()
        or active_mutes.filter(websites=alert.website).exists()
    ):
        logger.info("Alert %s suppressed — mute window active for %s", alert.id, alert.website.domain)
        return []

    # Dispatch per channel
    channels = NotificationChannel.objects.filter(user=user, enabled=True)
    sent_channels: list[str] = []

    for channel in channels:
        if not channel.matches(alert.severity, alert.alert_type):
            continue
        provider = get_provider(channel)
        if provider is None:
            logger.warning("No provider for channel type %s", channel.channel_type)
            continue
        try:
            success = provider.send(alert, user)
        except Exception:
            logger.exception("Provider %s raised for alert %s", channel.channel_type, alert.id)
            success = False
        if success:
            sent_channels.append(channel.channel_type)

    # Persist
    if sent_channels:
        existing = set(alert.notification_channels_sent or [])
        existing.update(sent_channels)
        alert.notification_channels_sent = list(existing)
        alert.save(update_fields=["notification_channels_sent", "updated_at"])

    return sent_channels
