from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from subscriptions.models import Plan, Subscription


def create_plans():
    Plan.objects.get_or_create(
        tier=Plan.Tier.FREE,
        defaults={"name": "Free", "price_monthly": 0, "max_websites": 1},
    )
    Plan.objects.get_or_create(
        tier=Plan.Tier.PRO,
        defaults={"name": "Pro", "price_monthly": 19, "max_websites": 10},
    )
    Plan.objects.get_or_create(
        tier=Plan.Tier.BUSINESS,
        defaults={"name": "Business", "price_monthly": 49, "max_websites": 50},
    )


class PlanModelTest(TestCase):
    def setUp(self):
        create_plans()

    def test_plans_created(self):
        self.assertEqual(Plan.objects.count(), 3)

    def test_free_plan_price(self):
        free = Plan.objects.get(tier=Plan.Tier.FREE)
        self.assertEqual(free.price_monthly, 0)

    def test_str(self):
        plan = Plan.objects.get(tier=Plan.Tier.PRO)
        self.assertIn("pro", str(plan))


class SubscriptionSignalTest(TestCase):
    def setUp(self):
        create_plans()

    def test_free_subscription_created_on_user_creation(self):
        user = User.objects.create_user(email="sub@test.com", password="pass1234")
        self.assertTrue(Subscription.objects.filter(user=user).exists())
        sub = Subscription.objects.get(user=user)
        self.assertEqual(sub.plan.tier, Plan.Tier.FREE)
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)

    def test_no_duplicate_on_update(self):
        user = User.objects.create_user(email="sub2@test.com", password="pass1234")
        user.full_name = "Updated"
        user.save()
        self.assertEqual(Subscription.objects.filter(user=user).count(), 1)


class SubscriptionMethodsTest(TestCase):
    def setUp(self):
        create_plans()
        self.user = User.objects.create_user(email="sub3@test.com", password="pass1234")
        self.sub = Subscription.objects.get(user=self.user)

    def test_is_active_true(self):
        self.assertTrue(self.sub.is_active)

    def test_is_free_true(self):
        self.assertTrue(self.sub.is_free)

    def test_cancel(self):
        pro = Plan.objects.get(tier=Plan.Tier.PRO)
        self.sub.plan = pro
        self.sub.save()
        self.sub.cancel()
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, Subscription.Status.CANCELLED)
        self.assertIsNotNone(self.sub.cancelled_at)

    def test_is_active_false_when_cancelled(self):
        pro = Plan.objects.get(tier=Plan.Tier.PRO)
        self.sub.plan = pro
        self.sub.save()
        self.sub.cancel()
        self.assertFalse(self.sub.is_active)


class UpgradeEndpointTest(TestCase):
    """The upgrade endpoint must never grant a paid plan without payment."""

    def setUp(self):
        create_plans()
        self.user = User.objects.create_user(
            email="upgrade@test.com", password="pass1234"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @override_settings(BILLING_ENABLED=False, BILLING_PROVIDER="")
    def test_upgrade_is_disabled_when_billing_not_configured(self):
        response = self.client.post(
            "/api/v1/subscriptions/upgrade/",
            {"plan_tier": Plan.Tier.BUSINESS, "billing_cycle": "yearly"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "billing_not_configured")
        self.assertEqual(
            Subscription.objects.get(user=self.user).plan.tier, Plan.Tier.FREE
        )

    @override_settings(BILLING_ENABLED=True, BILLING_PROVIDER="")
    def test_upgrade_is_disabled_without_a_provider(self):
        response = self.client.post(
            "/api/v1/subscriptions/upgrade/",
            {"plan_tier": Plan.Tier.PRO},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            Subscription.objects.get(user=self.user).plan.tier, Plan.Tier.FREE
        )
