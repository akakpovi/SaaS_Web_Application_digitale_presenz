"""Tests for the notification-channel test endpoint.

``POST /api/v1/notifications/channels/{id}/test/`` used to return a success
message without ever contacting the provider, so a broken SMTP configuration
looked perfectly healthy.  It now performs a real delivery and reports failure.
"""

from django.core import mail
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from notifications.models import NotificationChannel


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NotificationChannelTestEndpointTests(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="notify@example.com", password="pass1234!")
        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        mail.outbox.clear()

    def _email_channel(self) -> NotificationChannel:
        return NotificationChannel.objects.get(
            user=self.user, channel_type=NotificationChannel.ChannelType.EMAIL
        )

    def test_test_endpoint_sends_a_real_email(self) -> None:
        channel = self._email_channel()

        response = self.client.post(f"/api/v1/notifications/channels/{channel.pk}/test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_test_endpoint_reports_delivery_failure(self) -> None:
        """An unreachable SMTP relay must surface as a failure, not a success."""
        channel = self._email_channel()

        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
            EMAIL_HOST="127.0.0.1",
            EMAIL_PORT=1,
            EMAIL_TIMEOUT=1,
            EMAIL_USE_TLS=False,
        ):
            response = self.client.post(f"/api/v1/notifications/channels/{channel.pk}/test/")

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(mail.outbox, [])

    def test_rejects_a_channel_without_a_supported_provider(self) -> None:
        channel = NotificationChannel.objects.create(
            user=self.user,
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            name="Webhook",
            config={},
        )

        response = self.client.post(f"/api/v1/notifications/channels/{channel.pk}/test/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_a_slack_channel_without_webhook_url(self) -> None:
        channel = NotificationChannel.objects.create(
            user=self.user,
            channel_type=NotificationChannel.ChannelType.SLACK,
            name="Slack",
            config={},
        )

        response = self.client.post(f"/api/v1/notifications/channels/{channel.pk}/test/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("webhook_url", str(response.data))

    def test_cannot_test_another_users_channel(self) -> None:
        outsider = User.objects.create_user(email="outsider@example.com", password="pass1234!")
        channel = NotificationChannel.objects.get(
            user=outsider, channel_type=NotificationChannel.ChannelType.EMAIL
        )

        response = self.client.post(f"/api/v1/notifications/channels/{channel.pk}/test/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DefaultEmailChannelSignalTests(TestCase):
    def test_every_new_user_gets_one_enabled_email_channel(self) -> None:
        user = User.objects.create_user(email="fresh@example.com", password="pass1234!")

        channels = NotificationChannel.objects.filter(
            user=user, channel_type=NotificationChannel.ChannelType.EMAIL
        )
        self.assertEqual(channels.count(), 1)
        self.assertTrue(channels.get().enabled)
