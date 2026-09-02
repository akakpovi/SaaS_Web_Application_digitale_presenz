"""Notification providers (email, Slack, webhook, etc.)."""

import logging
from abc import ABC, abstractmethod
from typing import Optional

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
                from_email='noreply@presence.local',
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
        
        import requests
        webhook_url = self.channel.config.get('webhook_url')
        if not webhook_url:
            return False
        
        try:
            requests.post(webhook_url, json={
                'text': f"*{alert.title}*\n{alert.message}",
                'severity': alert.severity,
            }, timeout=5)
            logger.info(f"Slack message sent for {alert.alert_type}")
            return True
        except Exception as e:
            logger.exception("Slack send failed")
            return False
    
    def validate_config(self) -> list[str]:
        errors = []
        if not self.channel or not self.channel.config.get('webhook_url'):
            errors.append("webhook_url is required")
        return errors


class WebhookProvider(NotificationProvider):
    """Send alerts to custom webhook."""
    
    def send(self, alert, user) -> bool:
        if not self.channel:
            return False
        
        import requests
        webhook_url = self.channel.config.get('webhook_url')
        if not webhook_url:
            return False
        
        try:
            requests.post(webhook_url, json={
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'title': alert.title,
                'message': alert.message,
                'website': alert.website.domain,
            }, timeout=5)
            logger.info(f"Webhook sent for {alert.alert_type}")
            return True
        except Exception as e:
            logger.exception("Webhook send failed")
            return False
    
    def validate_config(self) -> list[str]:
        errors = []
        if not self.channel or not self.channel.config.get('webhook_url'):
            errors.append("webhook_url is required")
        return errors


class DiscordProvider(WebhookProvider):
    """Send alerts to Discord (also uses webhooks)."""
    pass


PROVIDER_MAP = {
    'email': EmailProvider,
    'slack': SlackProvider,
    'webhook': WebhookProvider,
    'discord': DiscordProvider,
    'sms': NotificationProvider,
}


def get_provider(channel) -> Optional[NotificationProvider]:
    """Get provider instance for a notification channel."""
    if not channel:
        return None
    
    provider_cls = PROVIDER_MAP.get(channel.channel_type)
    if not provider_cls:
        return None
    
    return provider_cls(channel=channel)
