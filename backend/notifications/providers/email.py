import logging

from django.conf import settings
from django.core.mail import send_mail

from .base import NotificationProvider

logger = logging.getLogger(__name__)

ICONS = {"critical": "🔴", "warning": "🟡", "info": "🔵"}


class EmailNotificationProvider(NotificationProvider):
    def validate_config(self) -> list[str]:
        errors = []
        if not self.config.get("email"):
            errors.append("'email' is required in config")
        return errors

    def send(self, alert, user) -> bool:
        recipient = self.config.get("email") or user.email
        icon = ICONS.get(alert.severity, "⚪")
        subject = f"{icon} [{alert.severity.upper()}] {alert.title}"
        body = (
            f"{alert.message}\n\n"
            f"Website : {alert.website.domain}\n"
            f"Type    : {alert.alert_type}\n"
            f"Severity: {alert.severity}\n"
        )
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
            return True
        except Exception:
            logger.exception("EmailNotificationProvider failed for alert %s", alert.id)
            return False
