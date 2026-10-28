from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User
from notifications.models import WebPushSubscription

PUBLIC_KEY_URL = "/api/v1/notifications/push/public-key/"
SUBSCRIBE_URL = "/api/v1/notifications/push/subscribe/"
TEST_URL = "/api/v1/notifications/push/test/"


class PushPublicKeyTests(TestCase):
    def test_returns_the_configured_public_key(self):
        with override_settings(VAPID_PUBLIC_KEY="BPublicKeyTest"):
            response = self.client.get(PUBLIC_KEY_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"public_key": "BPublicKeyTest", "configured": True}
        )

    def test_reports_a_missing_configuration(self):
        with override_settings(VAPID_PUBLIC_KEY=""):
            response = self.client.get(PUBLIC_KEY_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"public_key": "", "configured": False})


class PushSubscribeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="push@test.com", password="pass1234")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.payload = {
            "endpoint": "https://push.example.com/subscription/1",
            "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
        }

    def test_requires_authentication(self):
        anonymous = APIClient()
        self.assertEqual(anonymous.get(PUBLIC_KEY_URL).status_code, 200)
        response = anonymous.post(SUBSCRIBE_URL, self.payload, format="json")
        self.assertEqual(response.status_code, 401)

    def test_stores_the_browser_subscription(self):
        response = self.client.post(SUBSCRIBE_URL, self.payload, format="json")

        self.assertEqual(response.status_code, 201)
        subscription = WebPushSubscription.objects.get(user=self.user)
        self.assertEqual(subscription.endpoint, self.payload["endpoint"])
        self.assertEqual(subscription.p256dh, "p256dh-key")

    def test_rejects_incomplete_payload(self):
        response = self.client.post(
            SUBSCRIBE_URL, {"endpoint": "https://push.example.com/1"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(WebPushSubscription.objects.exists())

    def test_test_push_without_any_subscription_reports_it(self):
        response = self.client.post(TEST_URL, {"scenario": "down"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["status"], "no_subscription")
