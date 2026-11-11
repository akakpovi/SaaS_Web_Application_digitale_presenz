import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User
from notifications.models import NotificationChannel
from scans.models import Scan
from subscriptions.models import ApiKey, BillingEvent, Plan, Subscription
from subscriptions.pricing import PLAN_CATALOGUE
from websites.models import Website

PRO_PRICE = "pri_pro_monthly"
PRO_PRICE_YEARLY = "pri_pro_yearly"


def seed_plans():
    for entry in PLAN_CATALOGUE:
        Plan.objects.update_or_create(
            tier=entry["tier"],
            defaults={k: v for k, v in entry.items() if k != "tier"},
        )
    pro = Plan.objects.get(tier=Plan.Tier.PRO)
    pro.external_price_id_monthly = PRO_PRICE
    pro.external_price_id_yearly = PRO_PRICE_YEARLY
    pro.save(update_fields=["external_price_id_monthly", "external_price_id_yearly"])
    return Plan.objects.get(tier=Plan.Tier.PRO)


def make_user(email="billing@test.com"):
    return User.objects.create_user(email=email, password="pass1234")


def sign(body: bytes, secret: str = "whsec_test", timestamp: int | None = None):
    ts = timestamp or int(time.time())
    digest = hmac.new(
        secret.encode(), f"{ts}:".encode() + body, hashlib.sha256
    ).hexdigest()
    return f"ts={ts};h1={digest}"


BILLING_SETTINGS = dict(
    BILLING_ENABLED=True,
    BILLING_PROVIDER="paddle",
    PADDLE_API_KEY="pdl_test_key",
    PADDLE_WEBHOOK_SECRET="whsec_test",
    PADDLE_API_URL="https://sandbox-api.paddle.com",
    FRONTEND_URL="https://localhost",
)


@override_settings(**BILLING_SETTINGS)
class CheckoutEndpointTest(TestCase):
    def setUp(self):
        seed_plans()
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_checkout_requires_auth(self):
        response = APIClient().post(
            "/api/v1/subscriptions/checkout/", {"plan_tier": "pro"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_free_plan_cannot_checkout(self):
        response = self.client.post(
            "/api/v1/subscriptions/checkout/",
            {"plan_tier": "free", "billing_cycle": "monthly"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_unknown_plan_is_rejected(self):
        response = self.client.post(
            "/api/v1/subscriptions/checkout/",
            {"plan_tier": "enterprise"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("subscriptions.services.billing.requests.post")
    def test_checkout_returns_provider_url(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "data": {
                "id": "txn_123",
                "checkout": {"url": "https://pay.paddle.io/checkout/txn_123"},
            }
        }
        mock_post.return_value = mock_response

        response = self.client.post(
            "/api/v1/subscriptions/checkout/",
            {"plan_tier": "pro", "billing_cycle": "monthly"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["checkout_url"], "https://pay.paddle.io/checkout/txn_123"
        )
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["items"], [{"price_id": PRO_PRICE, "quantity": 1}])
        self.assertEqual(payload["custom_data"]["user_id"], str(self.user.pk))
        # No amount comes from the client.
        self.assertNotIn("amount", payload)

    @patch("subscriptions.services.billing.requests.post")
    def test_checkout_provider_failure_is_502(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        mock_post.return_value = mock_response

        response = self.client.post(
            "/api/v1/subscriptions/checkout/",
            {"plan_tier": "pro"},
            format="json",
        )
        self.assertEqual(response.status_code, 502)

    def test_checkout_without_price_id_is_503(self):
        Plan.objects.filter(tier=Plan.Tier.PRO).update(
            external_price_id_monthly="", external_price_id_yearly=""
        )
        response = self.client.post(
            "/api/v1/subscriptions/checkout/",
            {"plan_tier": "pro"},
            format="json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "billing_not_configured")


@override_settings(BILLING_ENABLED=False, BILLING_PROVIDER="")
class CheckoutDisabledTest(TestCase):
    def setUp(self):
        seed_plans()
        self.user = make_user("disabled@test.com")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_checkout_disabled(self):
        response = self.client.post(
            "/api/v1/subscriptions/checkout/", {"plan_tier": "pro"}, format="json"
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "billing_not_configured")

    def test_portal_disabled(self):
        response = self.client.post("/api/v1/subscriptions/portal/")
        self.assertEqual(response.status_code, 503)

    def test_upgrade_is_closed(self):
        response = self.client.post(
            "/api/v1/subscriptions/upgrade/", {"plan_tier": "pro"}, format="json"
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            Subscription.objects.get(user=self.user).plan.tier, Plan.Tier.FREE
        )


@override_settings(
    BILLING_ENABLED=True,
    BILLING_PROVIDER="paddle",
    PADDLE_WEBHOOK_SECRET="whsec_test",
)
class UpgradeEnabledStillClosedTest(TestCase):
    def setUp(self):
        seed_plans()
        self.user = make_user("upgrade-enabled@test.com")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_upgrade_never_changes_the_plan(self):
        response = self.client.post(
            "/api/v1/subscriptions/upgrade/",
            {"plan_tier": "business", "billing_cycle": "yearly"},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "use_checkout")
        self.assertEqual(
            Subscription.objects.get(user=self.user).plan.tier, Plan.Tier.FREE
        )


def subscription_payload(user, event_sub_id="sub_123", status="active"):
    return {
        "event_id": "evt_001",
        "event_type": "subscription.created",
        "data": {
            "id": event_sub_id,
            "customer_id": "ctm_1",
            "status": status,
            "items": [{"price": {"id": PRO_PRICE}}],
            "custom_data": {"user_id": str(user.pk)},
            "current_billing_period": {
                "starts_at": "2026-10-01T00:00:00Z",
                "ends_at": "2026-11-01T00:00:00Z",
            },
        },
    }


@override_settings(**BILLING_SETTINGS)
class PaddleWebhookTest(TestCase):
    def setUp(self):
        seed_plans()
        self.user = make_user("webhook@test.com")
        self.client = APIClient()

    def post_event(self, payload, signature=None, timestamp=None):
        body = json.dumps(payload).encode()
        header = signature if signature is not None else sign(body, timestamp=timestamp)
        return self.client.post(
            "/api/v1/webhooks/paddle/",
            data=body,
            content_type="application/json",
            HTTP_PADDLE_SIGNATURE=header,
        )

    def test_missing_signature_is_rejected(self):
        payload = subscription_payload(self.user)
        body = json.dumps(payload).encode()
        response = self.client.post(
            "/api/v1/webhooks/paddle/", data=body, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(BillingEvent.objects.count(), 0)

    def test_invalid_signature_is_rejected(self):
        payload = subscription_payload(self.user)
        response = self.post_event(payload, signature="ts=1;h1=deadbeef")
        self.assertEqual(response.status_code, 400)

    def test_expired_timestamp_is_rejected(self):
        payload = subscription_payload(self.user)
        response = self.post_event(payload, timestamp=int(time.time()) - 3600)
        self.assertEqual(response.status_code, 400)

    def test_subscription_created_activates_plan(self):
        response = self.post_event(subscription_payload(self.user))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "processed")

        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan.tier, Plan.Tier.PRO)
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        self.assertEqual(sub.external_id, "sub_123")
        self.assertEqual(sub.billing_provider, "paddle")
        self.assertEqual(sub.billing_cycle, Subscription.BillingCycle.MONTHLY)
        self.assertIsNotNone(sub.current_period_end)
        self.assertEqual(sub.billing_metadata["customer_id"], "ctm_1")

    def test_duplicate_event_is_idempotent(self):
        payload = subscription_payload(self.user)
        first = self.post_event(payload)
        second = self.post_event(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["status"], "duplicate")
        self.assertEqual(BillingEvent.objects.count(), 1)

    def test_cancelled_event_downgrades_status(self):
        self.post_event(subscription_payload(self.user))
        payload = subscription_payload(self.user, status="canceled")
        payload["event_id"] = "evt_cancel"
        payload["event_type"] = "subscription.canceled"

        response = self.post_event(payload)
        self.assertEqual(response.status_code, 200)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.status, Subscription.Status.CANCELLED)
        self.assertIsNotNone(sub.cancelled_at)

    def test_transaction_completed_provisions_subscription(self):
        payload = {
            "event_id": "evt_txn",
            "event_type": "transaction.completed",
            "data": {
                "id": "txn_9",
                "status": "completed",
                "subscription_id": "sub_txn",
                "customer_id": "ctm_txn",
                "custom_data": {"user_id": str(self.user.pk)},
                "items": [{"price_id": PRO_PRICE}],
                "billing_period": {
                    "starts_at": "2026-10-01T00:00:00Z",
                    "ends_at": "2026-11-01T00:00:00Z",
                },
            },
        }
        response = self.post_event(payload)
        self.assertEqual(response.status_code, 200)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan.tier, Plan.Tier.PRO)
        self.assertEqual(sub.external_id, "sub_txn")

    def test_unknown_price_fails_loudly(self):
        payload = subscription_payload(self.user)
        payload["data"]["items"][0]["price"]["id"] = "pri_unknown"
        response = self.post_event(payload)
        self.assertEqual(response.status_code, 500)
        event = BillingEvent.objects.get(event_id="evt_001")
        self.assertEqual(event.status, BillingEvent.Status.FAILED)


@override_settings(**BILLING_SETTINGS)
class ApiKeyTest(TestCase):
    def setUp(self):
        seed_plans()
        self.user = make_user("apikey@test.com")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_free_plan_cannot_create_api_key(self):
        response = self.client.post("/api/v1/api-keys/", {"name": "CI"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ApiKey.objects.filter(user=self.user).exists())

    def test_paid_plan_can_create_and_use_api_key(self):
        sub = Subscription.objects.get(user=self.user)
        sub.plan = Plan.objects.get(tier=Plan.Tier.PRO)
        sub.status = Subscription.Status.ACTIVE
        sub.save()

        response = self.client.post("/api/v1/api-keys/", {"name": "CI"}, format="json")
        self.assertEqual(response.status_code, 201)
        raw_key = response.data["api_key"]
        self.assertTrue(raw_key.startswith("pk_"))
        self.assertNotIn("hashed_key", response.data)

        authed = APIClient()
        authed.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}")
        me = authed.get("/api/v1/subscriptions/me/")
        self.assertEqual(me.status_code, 200)

        revoke = self.client.delete(f"/api/v1/api-keys/{response.data['id']}/")
        self.assertEqual(revoke.status_code, 204)

        revoked = APIClient()
        revoked.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}")
        self.assertEqual(revoked.get("/api/v1/subscriptions/me/").status_code, 401)


@override_settings(BILLING_ENABLED=False, BILLING_PROVIDER="")
class QuotaEnforcementTest(TestCase):
    def setUp(self):
        seed_plans()
        self.user = make_user("quota@test.com")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_free_plan_allows_only_one_website(self):
        first = self.client.post(
            "/api/v1/websites/", {"domain": "one.example.com"}, format="json"
        )
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            "/api/v1/websites/", {"domain": "two.example.com"}, format="json"
        )
        self.assertEqual(second.status_code, 403)
        self.assertEqual(second.data["code"], "website_limit_reached")
        self.assertFalse(Website.objects.filter(domain="two.example.com").exists())

    def test_pro_plan_raises_website_limit(self):
        sub = Subscription.objects.get(user=self.user)
        sub.plan = Plan.objects.get(tier=Plan.Tier.PRO)
        sub.save()
        sub.refresh_from_db()
        self.assertEqual(sub.plan.tier, Plan.Tier.PRO, "plan did not persist")

        for i in range(3):
            response = self.client.post(
                "/api/v1/websites/", {"domain": f"site{i}.example.com"}, format="json"
            )
            self.assertEqual(response.status_code, 201, response.data)

    def test_scan_quota_is_enforced(self):
        website = Website.objects.create(owner=self.user, domain="scan.example.com")
        for i in range(10):
            Scan.objects.create(
                website=website,
                trigger=Scan.Trigger.MANUAL,
                status=Scan.Status.COMPLETED,
            )

        response = self.client.post(f"/api/v1/websites/{website.id}/scan/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "scan_quota_exceeded")
        self.assertEqual(response.data["limit"], 10)

    def test_scan_quota_allows_under_limit(self):
        website = Website.objects.create(owner=self.user, domain="ok.example.com")
        for i in range(9):
            Scan.objects.create(
                website=website,
                trigger=Scan.Trigger.MANUAL,
                status=Scan.Status.COMPLETED,
            )

        with patch("websites.views.run_authenticated_scan.delay"):
            response = self.client.post(f"/api/v1/websites/{website.id}/scan/")
        self.assertEqual(response.status_code, 202)

    def test_free_plan_cannot_export_pdf(self):
        website = Website.objects.create(owner=self.user, domain="pdf.example.com")
        scan = Scan.objects.create(
            website=website,
            trigger=Scan.Trigger.MANUAL,
            status=Scan.Status.COMPLETED,
        )
        response = self.client.get(f"/api/v1/reports/pdf/{scan.id}/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "can_export_reports_required")

    def test_alert_channel_quota_is_enforced(self):
        # The free plan ships one default e-mail channel, which already fills
        # the single allowed slot.
        self.assertEqual(NotificationChannel.objects.filter(user=self.user).count(), 1)
        response = self.client.post(
            "/api/v1/notifications/channels/",
            {
                "channel_type": "slack",
                "name": "Ops",
                "config": {"webhook_url": "https://hooks.slack.com/services/T/B/x"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "alert_channel_limit_reached")
