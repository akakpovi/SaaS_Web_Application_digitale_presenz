"""Notification providers (email, Slack, webhook, etc.)."""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from core.security import DomainValidationError, safe_webhook_request

logger = logging.getLogger(__name__)


class NotificationProvider(ABC):
    """Base class for notification providers."""

    def __init__(self, channel=None):
        self.channel = channel

    @abstractmethod
    def send(self, alert, user) -> bool:
        """Send alert. Return True if successful."""
        pass

    @abstractmethod
    def validate_config(self) -> list[str]:
        """Validate channel config. Return list of errors (empty = valid)."""
        pass


class EmailProvider(NotificationProvider):
    """Send alerts via email."""

    def send(self, alert, user) -> bool:
        from django.core.mail import send_mail

        try:
            send_mail(
                subject=alert.title,
                message=alert.message,
                from_email="noreply@presence.local",
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info(f"Email sent to {user.email} for {alert.alert_type}")
            return True
        except Exception as e:
            logger.exception("Email send failed")
            return False

    def validate_config(self) -> list[str]:
        return []


class SlackProvider(NotificationProvider):
    """Send alerts to Slack webhook."""

    def send(self, alert, user) -> bool:
        if not self.channel:
            return False

        webhook_url = self.channel.config.get("webhook_url")
        if not webhook_url:
            return False

        try:
            # SSRF-safe POST: validates the URL and pins the connection to a
            # pre-resolved public IP (blocks loopback/private/metadata targets).
            safe_webhook_request(
                webhook_url,
                json_payload={
                    "text": f"*{alert.title}*\n{alert.message}",
                    "severity": alert.severity,
                },
                connect_timeout=5.0,
                read_timeout=5.0,
            )
            logger.info(f"Slack message sent for {alert.alert_type}")
            return True
        except DomainValidationError:
            logger.warning("Slack webhook blocked by SSRF validation: %s", webhook_url)
            return False
        except Exception:
            logger.exception("Slack send failed")
            return False

    def validate_config(self) -> list[str]:
        errors = []
        if not self.channel or not self.channel.config.get("webhook_url"):
            errors.append("webhook_url is required")
        return errors


class WebhookProvider(NotificationProvider):
    """Send alerts to custom webhook."""

    def send(self, alert, user) -> bool:
        if not self.channel:
            return False

        webhook_url = self.channel.config.get("webhook_url")
        if not webhook_url:
            return False

        try:
            # SSRF-safe POST: user-supplied webhook URLs must never reach
            # internal services. safe_webhook_request validates the hostname
            # and connects only to a pre-validated public IP.
            safe_webhook_request(
                webhook_url,
                json_payload={
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "title": alert.title,
                    "message": alert.message,
                    "website": alert.website.domain,
                },
                connect_timeout=5.0,
                read_timeout=5.0,
            )
            logger.info(f"Webhook sent for {alert.alert_type}")
            return True
        except DomainValidationError:
            logger.warning("Webhook blocked by SSRF validation: %s", webhook_url)
            return False
        except Exception:
            logger.exception("Webhook send failed")
            return False

    def validate_config(self) -> list[str]:
        errors = []
        if not self.channel or not self.channel.config.get("webhook_url"):
            errors.append("webhook_url is required")
        return errors


class DiscordProvider(WebhookProvider):
    """Send alerts to Discord (also uses webhooks)."""

    pass


PROVIDER_MAP = {
    "email": EmailProvider,
    "slack": SlackProvider,
    "webhook": WebhookProvider,
    "discord": DiscordProvider,
    "sms": NotificationProvider,
}


def get_provider(channel) -> Optional[NotificationProvider]:
    """Get provider instance for a notification channel."""
    if not channel:
        return None

    provider_cls = PROVIDER_MAP.get(channel.channel_type)
    if not provider_cls:
        return None

    return provider_cls(channel=channel)
