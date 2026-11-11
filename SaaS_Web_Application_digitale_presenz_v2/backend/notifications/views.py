import logging
from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import NotificationChannel, WebPushSubscription
from .serializers import NotificationChannelSerializer

logger = logging.getLogger(__name__)


class NotificationChannelListCreateView(generics.ListCreateAPIView):
    serializer_class = NotificationChannelSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return NotificationChannel.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        from subscriptions.services.quotas import assert_can_add_alert_channel

        assert_can_add_alert_channel(self.request.user)
        serializer.save(user=self.request.user)


class NotificationChannelDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = NotificationChannelSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return NotificationChannel.objects.filter(user=self.request.user)


class _TestAlert:
    """Minimal stand-in for an ``Alert`` so providers can be exercised directly."""

    id = "test-notification"
    severity = "info"
    alert_type = "test_notification"
    title = "Presence test notification"
    message = "This is a test notification sent from your Presence dashboard."
    created_at = None

    class _Website:
        domain = "test.presence.local"

    website = _Website()


class TestNotificationChannelView(APIView):
    """POST /api/v1/notifications/channels/{id}/test/

    Actually delivers a test notification through the channel.  The previous
    implementation only returned a success message without ever contacting the
    provider, so a misconfigured channel looked healthy.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from notifications.providers import get_provider

        try:
            channel = NotificationChannel.objects.get(pk=pk, user=request.user)
        except NotificationChannel.DoesNotExist:
            return Response(
                {"detail": "Canal introuvable."}, status=status.HTTP_404_NOT_FOUND
            )

        provider = get_provider(channel)
        if provider is None:
            return Response(
                {
                    "detail": f"Type de canal non pris en charge : {channel.channel_type}."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        errors = provider.validate_config()
        if errors:
            return Response(
                {"detail": "Configuration du canal invalide.", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not provider.send(_TestAlert(), request.user):
            logger.warning("Test notification failed for channel %s", channel.pk)
            return Response(
                {
                    "detail": f"Échec de l'envoi via « {channel.name} ». Vérifiez la configuration."
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "status": "success",
                "message": f"Notification de test envoyée via « {channel.name} ».",
            }
        )


class PushPublicKeyView(APIView):
    """GET /api/v1/notifications/push/public-key/

    The VAPID public key the browser needs to create a push subscription.  It
    is public by design (it is sent with every push message); the private key
    never leaves the server.  Returning an explicit ``configured`` flag lets
    the UI explain a missing configuration instead of failing inside
    ``pushManager.subscribe`` with an opaque browser error.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        public_key = getattr(settings, "VAPID_PUBLIC_KEY", "")
        return Response({"public_key": public_key, "configured": bool(public_key)})


class SubscribePushView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        endpoint = data.get("endpoint")
        keys = data.get("keys", {})
        p256dh = keys.get("p256dh")
        auth = keys.get("auth")

        if not endpoint or not p256dh or not auth:
            return Response(
                {"detail": "Données push invalides."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sub, created = WebPushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": p256dh,
                "auth": auth,
            },
        )
        return Response(
            {"status": "subscribed", "created": created}, status=status.HTTP_201_CREATED
        )


class TestPushNotificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        scenario = request.data.get("scenario", "down")
        user = request.user

        scenarios = {
            "down": {
                "title": "🚨 ALERTE CRITIQUE : Site Inaccessible !",
                "body": "Votre site google.com ne répond plus (Erreur 502 Bad Gateway). Cliquez pour diagnostiquer.",
                "url": "/app/monitoring",
            },
            "ssl": {
                "title": "⚠️ ATTENTION SSL : Expiration imminente",
                "body": "Le certificat SSL de allopneus.com expire dans 5 jours. Renouvellement requis.",
                "url": "/app/websites",
            },
            "seo": {
                "title": "🎉 NOUVEAU SCORE : Audit SEO Terminé",
                "body": "Félicitations ! Votre santé SEO globale pour decathlon.fr est montée à 92/100.",
                "url": "/app/seo",
            },
        }

        config = scenarios.get(scenario, scenarios["down"])

        try:
            from notifications.services.webpush import send_web_push_notification

            result = send_web_push_notification(
                user=user, title=config["title"], body=config["body"], url=config["url"]
            )
            return Response(
                {
                    "status": "success",
                    "scenario": scenario,
                    "result": result,
                    "message": f"Notification '{scenario}' envoyée.",
                }
            )
        except Exception as e:
            logger.error(f"Erreur push: {e}")
            return Response(
                {"status": "error", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
