from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class NotificationChannel(models.Model):
    class ChannelType(models.TextChoices):
        EMAIL = "email", "Email"
        SLACK = "slack", "Slack"
        DISCORD = "discord", "Discord"
        WEBHOOK = "webhook", "Webhook"
        SMS = "sms", "SMS"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notification_channels"
    )
    channel_type = models.CharField(max_length=10, choices=ChannelType.choices)
    name = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)
    config = models.JSONField(
        default=dict, help_text='e.g. {"webhook_url": "https://..."}'
    )

    # Filters — empty list = accept all
    severities = models.JSONField(
        default=list, help_text='["critical","warning"] or [] = all'
    )
    alert_types = models.JSONField(
        default=list, help_text='["ssl_expired"] or [] = all'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["channel_type", "name"]
        verbose_name = "Notification Channel"

    def __str__(self) -> str:
        return f"NotificationChannel({self.channel_type}, {self.name})"

    def matches(self, severity: str, alert_type: str) -> bool:
        """Return True if this channel should receive this alert."""
        if self.severities and severity not in self.severities:
            return False
        if self.alert_types and alert_type not in self.alert_types:
            return False
        return True


class WebPushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
