from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import NotificationChannel
from notifications.providers import get_provider
from notifications.serializers import NotificationChannelSerializer


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
    """POST /api/v1/notifications/channels/<id>/test/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk) -> Response:
        channel = get_object_or_404(NotificationChannel, pk=pk, user=request.user)
        provider = get_provider(channel)

        if provider is None:
            return Response(
                {"detail": f"No provider for channel type '{channel.channel_type}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from alerts.models import Alert
        from websites.models import Website

        website = Website.objects.filter(owner=request.user).first()
        if not website:
            return Response(
                {"detail": "You must have at least one website to test a notification."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fake_alert = Alert(
            user=request.user, website=website,
            alert_type=Alert.AlertType.SCORE_DROP,
            severity=Alert.Severity.INFO,
            title="Test notification from Presence SaaS",
            message="This is a test notification to verify your channel is configured correctly.",
        )
        fake_alert.created_at = timezone.now()

        try:
            success = provider.send(fake_alert, request.user)
        except Exception as exc:
            return Response(
                {"detail": f"Provider raised an error: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if success:
            return Response({"detail": "Test notification sent successfully."})
        return Response(
            {"detail": "Failed to send. Check channel configuration."},
            status=status.HTTP_502_BAD_GATEWAY,
        )
