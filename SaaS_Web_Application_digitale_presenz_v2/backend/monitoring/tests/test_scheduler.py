"""Scheduled monitoring obeys the billing plan.

The scheduler used to queue a scan for every due website regardless of the
plan: a Free account could monitor at a 5-minute interval and consume an
unlimited number of scans, bypassing every quota enforced on the API.  These
tests lock the two rules now applied by ``run_due_monitors``:

* no scan once the monthly quota is exhausted;
* the configured interval is never shorter than the plan's minimum.
"""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from monitoring.models import MonitoringConfig
from monitoring.tasks import run_due_monitors
from scans.models import Scan
from subscriptions.models import Plan, Subscription
from websites.models import Website


class MonitoringQuotaTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="monitor@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(
            owner=self.user, domain="monitor-example.de"
        )
        self.config = MonitoringConfig.objects.get(website=self.website)
        self.config.enabled = True
        self.config.interval = MonitoringConfig.Interval.FIVE_MIN
        self.config.next_scan_at = timezone.now() - timedelta(minutes=1)
        self.config.save()

    def _plan(self, *, max_scans: int, interval: str = "1h") -> Plan:
        plan = Plan.objects.create(
            tier=Plan.Tier.FREE,
            name="Free test",
            max_scans_per_month=max_scans,
            min_scan_interval=interval,
        )
        Subscription.objects.create(user=self.user, plan=plan)
        return plan

    def test_quota_exhausted_blocks_the_scheduled_scan(self) -> None:
        self._plan(max_scans=1)
        Scan.objects.create(website=self.website, status=Scan.Status.COMPLETED)

        with mock.patch("scans.tasks.run_authenticated_scan.delay") as delay:
            result = run_due_monitors.apply().get()

        self.assertEqual(result["queued"], 0)
        self.assertEqual(result["quota_blocked"], 1)
        delay.assert_not_called()
        self.assertEqual(Scan.objects.filter(website=self.website).count(), 1)

        self.config.refresh_from_db()
        self.assertGreater(
            self.config.next_scan_at,
            timezone.now() + timedelta(hours=23),
        )

    def test_plan_minimum_interval_extends_the_schedule(self) -> None:
        self._plan(max_scans=100, interval="24h")

        with mock.patch("scans.tasks.run_authenticated_scan.delay") as delay:
            result = run_due_monitors.apply().get()

        self.assertEqual(result["queued"], 1)
        delay.assert_called_once()
        self.config.refresh_from_db()
        # 24 h minimum plus at most 5 min of jitter.
        self.assertGreaterEqual(
            self.config.next_scan_at,
            timezone.now() + timedelta(hours=23, minutes=55),
        )

    def test_quota_is_counted_once_per_queued_scan(self) -> None:
        """Two due sites share the owner's quota; the second must be blocked."""
        second = Website.objects.create(owner=self.user, domain="second-monitor.de")
        second_config = MonitoringConfig.objects.get(website=second)
        second_config.enabled = True
        second_config.next_scan_at = timezone.now() - timedelta(minutes=1)
        second_config.save()

        self._plan(max_scans=1)

        with mock.patch("scans.tasks.run_authenticated_scan.delay") as delay:
            result = run_due_monitors.apply().get()

        self.assertEqual(result["queued"], 1)
        self.assertEqual(result["quota_blocked"], 1)
        self.assertEqual(delay.call_count, 1)
        self.assertEqual(Scan.objects.count(), 1)

    def test_pausing_during_a_tick_does_not_rearm_the_schedule(self) -> None:
        """A pause that lands while the scheduler runs must win.

        The scheduler used to write ``next_scan_at`` unconditionally at the
        end of its iteration, so a website paused mid-tick kept a future
        check that could never run.
        """
        self._plan(max_scans=100, interval="1h")

        def pause_while_queuing(scan_id):
            MonitoringConfig.objects.filter(pk=self.config.pk).update(
                enabled=False, next_scan_at=None
            )

        with mock.patch(
            "scans.tasks.run_authenticated_scan.delay",
            side_effect=pause_while_queuing,
        ):
            result = run_due_monitors.apply().get()

        self.assertEqual(result["queued"], 1)
        self.config.refresh_from_db()
        self.assertFalse(self.config.enabled)
        self.assertIsNone(self.config.next_scan_at)


class MonitoringActivationApiTests(TestCase):
    """Activating, pausing and re-scheduling through the API."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="activate@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(owner=self.user, domain="activate.de")
        self.config = MonitoringConfig.objects.get(website=self.website)
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}"
        )
        self.url = f"/api/v1/monitoring/websites/{self.website.pk}/"

    def test_new_config_has_no_schedule(self) -> None:
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["enabled"])
        self.assertIsNone(response.data["next_scan_at"])

    def test_activating_schedules_the_first_check(self) -> None:
        response = self.client.patch(self.url, {"enabled": True}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.config.refresh_from_db()
        self.assertTrue(self.config.enabled)
        self.assertIsNotNone(self.config.next_scan_at)
        self.assertLessEqual(self.config.next_scan_at, timezone.now())

    def test_pausing_clears_the_schedule(self) -> None:
        self.config.enabled = True
        self.config.next_scan_at = timezone.now() + timedelta(hours=1)
        self.config.save()

        response = self.client.patch(self.url, {"enabled": False}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.config.refresh_from_db()
        self.assertFalse(self.config.enabled)
        self.assertIsNone(self.config.next_scan_at)

    def test_changing_interval_reschedules_from_now(self) -> None:
        self.config.enabled = True
        self.config.next_scan_at = timezone.now() - timedelta(hours=2)
        self.config.save()

        response = self.client.patch(self.url, {"interval": "6h"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.config.refresh_from_db()
        self.assertEqual(self.config.interval, "6h")
        self.assertGreater(
            self.config.next_scan_at,
            timezone.now() + timedelta(hours=5, minutes=50),
        )
