"""A zombie scan must not block its website's 409 guard forever."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from scans.models import Scan
from scans.tasks import reap_stale_scans
from websites.models import Website


class StaleScanReaperTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="reaper-scan@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(
            owner=self.user, domain="reaper-scan.example"
        )

    def _scan(self, status_value: str, minutes_old: int = 0) -> Scan:
        scan = Scan.objects.create(
            website=self.website,
            status=status_value,
            scan_type=Scan.ScanType.FULL,
        )
        if minutes_old:
            Scan.objects.filter(pk=scan.pk).update(
                updated_at=timezone.now() - timedelta(minutes=minutes_old)
            )
        return scan

    @override_settings(
        SCAN_REAP_RUNNING_AFTER_SECONDS=900,
        SCAN_REAP_QUEUED_AFTER_SECONDS=900,
    )
    def test_stale_running_scan_is_failed(self) -> None:
        scan = self._scan(Scan.Status.RUNNING, minutes_old=16)

        result = reap_stale_scans.apply().get()

        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.FAILED)
        self.assertIn("reaped automatically", scan.failure_message)
        self.assertIsNotNone(scan.completed_at)
        self.assertIsNotNone(scan.failed_at)
        self.assertEqual(result["reaped"], 1)

    @override_settings(
        SCAN_REAP_RUNNING_AFTER_SECONDS=900,
        SCAN_REAP_QUEUED_AFTER_SECONDS=900,
    )
    def test_fresh_running_scan_is_left_alone(self) -> None:
        scan = self._scan(Scan.Status.RUNNING, minutes_old=5)

        result = reap_stale_scans.apply().get()

        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.RUNNING)
        self.assertEqual(result["reaped"], 0)

    @override_settings(
        SCAN_REAP_RUNNING_AFTER_SECONDS=900,
        SCAN_REAP_QUEUED_AFTER_SECONDS=900,
    )
    def test_stale_queued_scan_is_failed(self) -> None:
        scan = self._scan(Scan.Status.QUEUED, minutes_old=20)

        reap_stale_scans.apply().get()

        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.FAILED)

    def test_thresholds_are_floored_to_five_minutes(self) -> None:
        # A misconfigured tiny value must not reap a scan Celery is still
        # allowed to run (hard limit 600 s).
        scan = self._scan(Scan.Status.RUNNING, minutes_old=4)
        with override_settings(SCAN_REAP_RUNNING_AFTER_SECONDS=1):
            result = reap_stale_scans.apply().get()

        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.RUNNING)
        self.assertEqual(result["reaped"], 0)

    def test_reaper_is_scheduled_in_beat(self) -> None:
        entry = settings.CELERY_BEAT_SCHEDULE["reap-stale-scans"]
        self.assertEqual(entry["task"], "scans.tasks.reap_stale_scans")
        self.assertEqual(entry["schedule"], 300.0)


class ReapedScanUnblocksTriggerTests(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="reaper-trigger@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(
            owner=self.user, domain="reaper-trigger.example"
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse("website-trigger-scan", kwargs={"pk": self.website.pk})

    @override_settings(
        SCAN_REAP_RUNNING_AFTER_SECONDS=900,
        SCAN_REAP_QUEUED_AFTER_SECONDS=900,
    )
    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_trigger_returns_202_after_the_zombie_is_reaped(self, delay) -> None:
        zombie = Scan.objects.create(website=self.website, status=Scan.Status.RUNNING)
        Scan.objects.filter(pk=zombie.pk).update(
            updated_at=timezone.now() - timedelta(minutes=16)
        )

        blocked = self.client.post(self.url)
        self.assertEqual(blocked.status_code, status.HTTP_409_CONFLICT)

        reap_stale_scans.apply().get()

        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        delay.assert_called_once()
