import logging

import requests

from .base import NotificationProvider

logger = logging.getLogger(__name__)

SEVERITY_COLOR = {"critical": "danger", "warning": "warning", "info": "good"}
SEVERITY_ICON = {
    "critical": ":rotating_light:",
    "warning": ":warning:",
    "info": ":information_source:",
}


class SlackNotificationProvider(NotificationProvider):
    def validate_config(self) -> list[str]:
        errors = []
        if not self.config.get("webhook_url"):
            errors.append("'webhook_url' is required in config")
        return errors

    def send(self, alert, user) -> bool:
        webhook_url = self.config.get("webhook_url")
        if not webhook_url:
            return False

        icon = SEVERITY_ICON.get(alert.severity, ":bell:")
        color = SEVERITY_COLOR.get(alert.severity, "#cccccc")
        created_ts = int(alert.created_at.timestamp()) if alert.created_at else 0

        payload = {
            "text": f"{icon} *[{alert.severity.upper()}]* {alert.title}",
            "attachments": [
                {
                    "color": color,
                    "fields": [
                        {
                            "title": "Website",
                            "value": alert.website.domain,
                            "short": True,
                        },
                        {"title": "Type", "value": alert.alert_type, "short": True},
                        {"title": "Message", "value": alert.message, "short": False},
                    ],
                    "footer": "Presence SaaS",
                    "ts": created_ts,
                }
            ],
        }
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("SlackNotificationProvider failed for alert %s", alert.id)
            return False
