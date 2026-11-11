"""Security regression tests for subscription endpoints.

The public contract is intentionally narrow:

* ``GET /subscriptions/me/`` returns only the authenticated user's row;
* there is no list or detail endpoint for selecting another user's UUID;
* ``PATCH /subscriptions/me/`` is not implemented;
* ``POST /subscriptions/upgrade/`` never changes a plan.

Plan changes must go through checkout + the signed payment webhook.
"""

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User
from subscriptions.models import Plan, Subscription


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
