from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from subscriptions.models import Plan, Subscription

URL = "/api/v1/analytics/admin/overview/"


class AdminOverviewMRRTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="staff@test.com", password="pass1234", is_staff=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def test_non_staff_is_forbidden(self):
        user = User.objects.create_user(email="user@test.com", password="pass1234")
        client = APIClient()
        client.force_authenticate(user)
        self.assertEqual(client.get(URL).status_code, 403)

    def test_mrr_normalises_yearly_plans_and_excludes_trial_and_free(self):
        pro = Plan.objects.create(
            tier=Plan.Tier.PRO,
            name="Pro",
            price_monthly=Decimal("29.00"),
            price_yearly=Decimal("290.00"),
        )
        free = Plan.objects.create(
            tier=Plan.Tier.FREE,
            name="Free",
            price_monthly=Decimal("0.00"),
            price_yearly=Decimal("0.00"),
        )

        monthly_user = User.objects.create_user(
            email="monthly@test.com", password="pass1234"
        )
        yearly_user = User.objects.create_user(
            email="yearly@test.com", password="pass1234"
        )
        trial_user = User.objects.create_user(
            email="trial@test.com", password="pass1234"
        )
        free_user = User.objects.create_user(email="free@test.com", password="pass1234")

        # Signup already provisions a free subscription (one-to-one), so the
        # fixtures update that row instead of inserting a second one.
        def subscribe(user, plan, status, cycle=Subscription.BillingCycle.MONTHLY):
            subscription, _ = Subscription.objects.get_or_create(
                user=user,
                defaults={"plan": plan, "status": status, "billing_cycle": cycle},
            )
            subscription.plan = plan
            subscription.status = status
            subscription.billing_cycle = cycle
            subscription.save()
            return subscription

        subscribe(monthly_user, pro, Subscription.Status.ACTIVE)
        subscribe(
            yearly_user,
            pro,
            Subscription.Status.ACTIVE,
            Subscription.BillingCycle.YEARLY,
        )
        subscribe(trial_user, pro, Subscription.Status.TRIALING)
        subscribe(free_user, free, Subscription.Status.ACTIVE)

        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)

        subscriptions = response.json()["subscriptions"]
        # 29.00 monthly + 290.00 / 12 yearly = 53.1666… → 53.17
        self.assertAlmostEqual(subscriptions["mrr_eur"], 53.17, places=2)
        self.assertAlmostEqual(subscriptions["arr_eur"], 638.0, places=1)
        self.assertEqual(subscriptions["paying_users"], 2)
        self.assertEqual(subscriptions["trialing_users"], 1)
        self.assertEqual(
            subscriptions["by_plan"],
            [{"tier": "pro", "name": "Pro", "count": 2, "mrr_eur": 53.17}],
        )
