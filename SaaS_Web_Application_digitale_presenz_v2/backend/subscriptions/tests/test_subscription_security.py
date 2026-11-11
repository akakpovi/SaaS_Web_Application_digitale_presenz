"""Security regression tests for subscription endpoints.

The public contract is intentionally narrow:

* ``GET /subscriptions/me/`` returns only the authenticated user's row;
* there is no list or detail endpoint for selecting another user's UUID;
* ``PATCH /subscriptions/me/`` is not implemented;
* ``POST /subscriptions/upgrade/`` never changes a plan.

Plan changes must go through checkout + the signed payment webhook.
"""

import hashlib
import hmac
import json
import time
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from subscriptions.models import BillingEvent, Plan, Subscription
from websites.models import Website


def paddle_signature(body: bytes, secret: str = "test-webhook-secret") -> str:
    timestamp = int(time.time())
    digest = hmac.new(
        secret.encode(), f"{timestamp}:".encode() + body, hashlib.sha256
    ).hexdigest()
    return f"ts={timestamp};h1={digest}"


class SubscriptionSecurityTest(TestCase):
    def setUp(self) -> None:
        self.free = Plan.objects.get_or_create(
            tier=Plan.Tier.FREE,
            defaults={
                "name": "Free",
                "max_websites": 1,
                "max_scans_per_month": 10,
            },
        )[0]
        self.pro = Plan.objects.get_or_create(
            tier=Plan.Tier.PRO,
            defaults={
                "name": "Pro",
                "max_websites": 10,
                "max_scans_per_month": 500,
            },
        )[0]
        self.user_a = User.objects.create_user(
            email="subscription-a@example.test", password="test-password-a"
        )
        self.user_b = User.objects.create_user(
            email="subscription-b@example.test", password="test-password-b"
        )
        self.sub_a = Subscription.objects.get(user=self.user_a)
        self.sub_b = Subscription.objects.get(user=self.user_b)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user_a)

    def test_me_requires_authentication(self) -> None:
        response = APIClient().get("/api/v1/subscriptions/me/")

        self.assertEqual(response.status_code, 401)

    def test_me_returns_only_the_authenticated_users_subscription(self) -> None:
        response = self.client.get("/api/v1/subscriptions/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["id"]), str(self.sub_a.id))
        self.assertNotEqual(str(response.data["id"]), str(self.sub_b.id))
        self.assertEqual(response.data["plan_tier"], Plan.Tier.FREE)

    def test_cannot_fetch_another_users_subscription_by_id(self) -> None:
        response = self.client.get(f"/api/v1/subscriptions/{self.sub_b.id}/")

        self.assertIn(response.status_code, (403, 404))

    def test_me_rejects_plan_changes(self) -> None:
        response = self.client.patch(
            "/api/v1/subscriptions/me/",
            {"plan_tier": Plan.Tier.PRO},
            format="json",
        )

        self.assertEqual(response.status_code, 405)
        self.sub_a.refresh_from_db()
        self.assertEqual(self.sub_a.plan.tier, Plan.Tier.FREE)

    @override_settings(
        BILLING_ENABLED=True,
        BILLING_PROVIDER="paddle",
        PADDLE_WEBHOOK_SECRET="test-webhook-secret",
    )
    def test_upgrade_endpoint_never_changes_the_plan(self) -> None:
        response = self.client.post(
            "/api/v1/subscriptions/upgrade/",
            {"plan_tier": Plan.Tier.PRO, "billing_cycle": "yearly"},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "use_checkout")
        self.sub_a.refresh_from_db()
        self.assertEqual(self.sub_a.plan.tier, Plan.Tier.FREE)


class PaidPlanSecurityTest(TestCase):
    """Paid entitlements must expire without granting Free users an upgrade."""

    def setUp(self) -> None:
        self.free = Plan.objects.get_or_create(
            tier=Plan.Tier.FREE,
            defaults={
                "name": "Free",
                "max_websites": 1,
                "max_scans_per_month": 10,
            },
        )[0]
        self.pro = Plan.objects.get_or_create(
            tier=Plan.Tier.PRO,
            defaults={
                "name": "Pro",
                "max_websites": 10,
                "max_scans_per_month": 500,
            },
        )[0]
        self.user = User.objects.create_user(
            email="paid-plan@example.test", password="test-password"
        )
        self.subscription = Subscription.objects.get(user=self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _set_subscription(self, **fields) -> None:
        Subscription.objects.filter(pk=self.subscription.pk).update(**fields)

    def test_expired_paid_plan_falls_back_to_free_website_quota(self) -> None:
        Website.objects.create(owner=self.user, domain="existing.example.test")
        self._set_subscription(
            plan=self.pro,
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() - timedelta(days=1),
        )

        response = self.client.post(
            "/api/v1/websites/",
            {"domain": "over-quota.example.test"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "website_limit_reached")
        self.assertEqual(response.data["plan"], Plan.Tier.FREE)
        self.assertEqual(response.data["limit"], 1)

    def test_cancelled_paid_plan_keeps_access_until_period_end(self) -> None:
        self._set_subscription(
            plan=self.pro,
            status=Subscription.Status.CANCELLED,
            current_period_end=timezone.now() + timedelta(days=30),
        )

        for index in range(2):
            response = self.client.post(
                "/api/v1/websites/",
                {"domain": f"paid-{index}.example.test"},
                format="json",
            )
            self.assertEqual(response.status_code, 201, response.data)


@override_settings(
    BILLING_ENABLED=True,
    BILLING_PROVIDER="paddle",
    PADDLE_WEBHOOK_SECRET="test-webhook-secret",
)
class PaddleWebhookSecurityTest(TestCase):
    """The public webhook must authenticate the exact raw body before writes."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.payload = {
            "event_id": "evt_security",
            "event_type": "subscription.created",
            "data": {"id": "sub_security"},
        }
        self.body = json.dumps(self.payload).encode()

    def _post(self, body: bytes, signature: str | None = None):
        headers = {}
        if signature is not None:
            headers["HTTP_PADDLE_SIGNATURE"] = signature
        return self.client.post(
            "/api/v1/webhooks/paddle/",
            data=body,
            content_type="application/json",
            **headers,
        )

    def test_missing_signature_is_rejected_without_persisting_event(self) -> None:
        response = self._post(self.body)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_signature")
        self.assertEqual(BillingEvent.objects.count(), 0)

    def test_invalid_signature_is_rejected_without_persisting_event(self) -> None:
        response = self._post(self.body, signature="ts=1;h1=deadbeef")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_signature")
        self.assertEqual(BillingEvent.objects.count(), 0)

    def test_signature_is_bound_to_the_raw_body(self) -> None:
        signature = paddle_signature(self.body)
        tampered = json.dumps(
            {
                "event_id": "evt_tampered",
                "event_type": "subscription.created",
                "data": {"id": "sub_tampered"},
            }
        ).encode()

        response = self._post(tampered, signature=signature)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_signature")
        self.assertEqual(BillingEvent.objects.count(), 0)

    def test_missing_webhook_secret_fails_closed(self) -> None:
        with self.settings(PADDLE_WEBHOOK_SECRET=""):
            response = self._post(self.body, signature="ts=1;h1=deadbeef")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "webhook_not_configured")
        self.assertEqual(BillingEvent.objects.count(), 0)
