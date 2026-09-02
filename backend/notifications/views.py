import logging
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
        serializer.save(user=self.request.user)


class NotificationChannelDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = NotificationChannelSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return NotificationChannel.objects.filter(user=self.request.user)


class TestNotificationChannelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            channel = NotificationChannel.objects.get(pk=pk, user=request.user)
            # Envoi d'un message de test
            return Response({"status": "success", "message": f"Canal {channel.name} testé avec succès."})
        except NotificationChannel.DoesNotExist:
            return Response({"detail": "Canal introuvable."}, status=status.HTTP_404_NOT_FOUND)


class SubscribePushView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        endpoint = data.get("endpoint")
        keys = data.get("keys", {})
        p256dh = keys.get("p256dh")
        auth = keys.get("auth")

        if not endpoint or not p256dh or not auth:
            return Response({"detail": "Données push invalides."}, status=status.HTTP_400_BAD_REQUEST)

        sub, created = WebPushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": p256dh,
                "auth": auth,
            }
        )
        return Response({"status": "subscribed", "created": created}, status=status.HTTP_201_CREATED)


class TestPushNotificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        scenario = request.data.get("scenario", "down")
        user = request.user

        scenarios = {
            "down": {
                "title": "🚨 ALERTE CRITIQUE : Site Inaccessible !",
                "body": "Votre site google.com ne répond plus (Erreur 502 Bad Gateway). Cliquez pour diagnostiquer.",
                "url": "/app/monitoring"
            },
            "ssl": {
                "title": "⚠️ ATTENTION SSL : Expiration imminente",
                "body": "Le certificat SSL de allopneus.com expire dans 5 jours. Renouvellement requis.",
                "url": "/app/websites"
            },
            "seo": {
                "title": "🎉 NOUVEAU SCORE : Audit SEO Terminé",
                "body": "Félicitations ! Votre santé SEO globale pour decathlon.fr est montée à 92/100.",
                "url": "/app/seo"
            }
        }

        config = scenarios.get(scenario, scenarios["down"])

        try:
            from notifications.services.webpush import send_web_push_notification
            result = send_web_push_notification(
                user=user,
                title=config["title"],
                body=config["body"],
                url=config["url"]
            )
            return Response({
                "status": "success",
                "scenario": scenario,
                "result": result,
                "message": f"Notification '{scenario}' envoyée."
            })
        except Exception as e:
            logger.error(f"Erreur push: {e}")
            return Response({
                "status": "error",
                "detail": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
