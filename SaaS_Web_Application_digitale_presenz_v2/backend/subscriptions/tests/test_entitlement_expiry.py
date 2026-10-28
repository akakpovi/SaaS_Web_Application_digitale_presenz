"""Paid entitlements end with the paid period.

No task ever expired a subscription, and ``get_effective_plan`` granted the
paid tier to ``past_due`` rows forever.  A failed renewal whose webhook was
lost therefore kept the paid limits indefinitely.  These tests pin the
period-based fallback and the daily expiry task.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from subscriptions.models import Plan, Subscription
from subscriptions.services.quotas import get_effective_plan
from subscriptions.tasks import expire_subscriptions


class EntitlementExpiryTests(TestCase):
    def setUp(self) -> None:
        self.free = Plan.objects.create(
            tier=Plan.Tier.FREE, name="Free", max_websites=1, max_scans_per_month=10
        )
        self.pro = Plan.objects.create(
            tier=Plan.Tier.PRO,
            name="Pro",
            price_monthly=19,
            max_websites=10,
            max_scans_per_month=500,
        )
        self.user = User.objects.create_user(
            email="billing@example.com", password="pass1234!"
        )
        self.sub = Subscription.objects.get(user=self.user)

    def _activate(self, status: str, period_end) -> None:
        self.sub.plan = self.pro
        self.sub.status = status
        self.sub.current_period_end = period_end
        self.sub.save()

    def test_active_subscription_inside_its_period_keeps_paid_plan(self) -> None:
        self._activate(
            Subscription.Status.ACTIVE, timezone.now() + timedelta(days=10)
        )
        self.assertEqual(get_effective_plan(self.user), self.pro)

    def test_past_due_inside_its_period_keeps_paid_plan(self) -> None:
        self._activate(
            Subscription.Status.PAST_DUE, timezone.now() + timedelta(days=2)
        )
        self.assertEqual(get_effective_plan(self.user), self.pro)

    def test_past_due_after_the_period_falls_back_to_free(self) -> None:
        self._activate(
            Subscription.Status.PAST_DUE, timezone.now() - timedelta(days=2)
        )
        self.assertEqual(get_effective_plan(self.user), self.free)

    def test_cancelled_keeps_paid_until_the_period_ends(self) -> None:
        self._activate(
            Subscription.Status.CANCELLED, timezone.now() + timedelta(days=5)
        )
        self.assertEqual(get_effective_plan(self.user), self.pro)

    def test_cancelled_after_the_period_falls_back_to_free(self) -> None:
        self._activate(
            Subscription.Status.CANCELLED, timezone.now() - timedelta(minutes=1)
        )
        self.assertEqual(get_effective_plan(self.user), self.free)

    def test_expiry_task_only_touches_ended_periods(self) -> None:
        self._activate(
            Subscription.Status.ACTIVE, timezone.now() - timedelta(hours=1)
        )
        active_user = User.objects.create_user(
            email="still-active@example.com", password="pass1234!"
        )
        active_sub = Subscription.objects.get(user=active_user)
        active_sub.plan = self.pro
        active_sub.status = Subscription.Status.ACTIVE
        active_sub.current_period_end = timezone.now() + timedelta(days=10)
        active_sub.save()

        result = expire_subscriptions.apply().get()

        self.assertEqual(result, {"expired": 1})
        self.sub.refresh_from_db()
        active_sub.refresh_from_db()
        self.assertEqual(self.sub.status, Subscription.Status.EXPIRED)
        self.assertEqual(active_sub.status, Subscription.Status.ACTIVE)

    def test_expired_subscription_never_grants_paid_limits(self) -> None:
        self._activate(
            Subscription.Status.EXPIRED, timezone.now() + timedelta(days=10)
        )
        self.assertEqual(get_effective_plan(self.user), self.free)
