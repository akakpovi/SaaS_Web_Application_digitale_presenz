import json
import logging
from pywebpush import webpush, WebPushException
from django.conf import settings
from notifications.models import WebPushSubscription

logger = logging.getLogger(__name__)

VAPID_PUBLIC_KEY = getattr(settings, "VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = getattr(settings, "VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS = {
    "sub": getattr(settings, "VAPID_CLAIMS_SUB", "mailto:support@presence.local")
}


def send_web_push_notification(
    user,
    title: str,
    body: str,
    url: str = "/app/dashboard",
    icon: str = "/icons/icon-192.svg",
) -> dict:
    subscriptions = WebPushSubscription.objects.filter(user=user)
    if not subscriptions.exists():
        logger.info(f"Aucun appareil enregistré pour {user.email}")
        return {"status": "no_subscription", "sent": 0, "failed": 0}

    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "url": url,
            "icon": icon,
        }
    )

    sent_count = 0
    failed_count = 0

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS,
            )
            sent_count += 1
            logger.info(f"✓ Notification push envoyée à {user.email}")
        except WebPushException as ex:
            logger.warning(f"Échec push: {ex}")
            failed_count += 1
            if ex.response and ex.response.status_code in [404, 410, 400]:
                sub.delete()
        except Exception as e:
            logger.error(f"Erreur inattendue webpush: {e}")
            failed_count += 1

    return {"status": "completed", "sent": sent_count, "failed": failed_count}
