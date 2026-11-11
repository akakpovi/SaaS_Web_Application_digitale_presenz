"""Scheduled scan policy and organization-scoped monitoring endpoints.

The scheduler used to create ``health`` scans only, whatever the customer
chose.  These tests pin the new behaviour: the website's configured scan type
is used, a website already scanning is skipped, the per-run cap holds, and the
monitoring endpoints respect organization membership instead of the legacy
``owner`` column.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from monitoring.models import MonitoringConfig
from monitoring.tasks import run_due_monitors
from organizations.models import Membership
from scans.models import Scan
from websites.models import Website


class SchedulerPolicyTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            email="policy@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(owner=self.owner, domain="policy.example")
        self.organization = self.website.organization
        self.config = MonitoringConfig.objects.get(website=self.website)
        self.config.enabled = True
        self.config.next_scan_at = timezone.now() - timedelta(minutes=1)
        self.config.save(update_fields=["enabled", "next_scan_at"])

    def run_scheduler(self, **overrides):
        with patch("scans.tasks.run_authenticated_scan.delay") as delay:
            with override_settings(**overrides):
                result = run_due_monitors()
        return result, delay

    def test_default_policy_stays_health(self):
        self.assertEqual(self.config.scan_type, MonitoringConfig.ScanPolicy.HEALTH)

        _result, delay = self.run_scheduler()

        scan = Scan.objects.get(website=self.website)
        self.assertEqual(scan.scan_type, Scan.ScanType.HEALTH)
        self.assertEqual(scan.trigger, Scan.Trigger.MONITORING)
        delay.assert_called_once_with(scan.pk)

    def test_configured_security_policy_is_used(self):
        self.config.scan_type = MonitoringConfig.ScanPolicy.SECURITY
        self.config.save(update_fields=["scan_type"])

        _result, _delay = self.run_scheduler()

        scan = Scan.objects.get(website=self.website)
        self.assertEqual(scan.scan_type, Scan.ScanType.SECURITY)

    def test_full_policy_is_used(self):
        self.config.scan_type = MonitoringConfig.ScanPolicy.FULL
        self.config.save(update_fields=["scan_type"])

        _result, _delay = self.run_scheduler()

        self.assertEqual(
            Scan.objects.get(website=self.website).scan_type, Scan.ScanType.FULL
        )

    def test_website_already_scanning_is_skipped(self):
        existing = Scan.objects.create(
            website=self.website,
            scan_type=Scan.ScanType.SECURITY,
            status=Scan.Status.RUNNING,
        )

        result, delay = self.run_scheduler()

        self.assertEqual(result["active"], 1)
        self.assertEqual(result["queued"], 0)
        delay.assert_not_called()
        self.assertEqual(Scan.objects.filter(website=self.website).count(), 1)
        self.assertEqual(existing.status, Scan.Status.RUNNING)

    def test_per_run_cap_limits_queued_scans(self):
        second = Website.objects.create(owner=self.owner, domain="policy-two.example")
        config = MonitoringConfig.objects.get(website=second)
        config.enabled = True
        config.next_scan_at = timezone.now() - timedelta(minutes=1)
        config.save(update_fields=["enabled", "next_scan_at"])

        result, _delay = self.run_scheduler(MONITORING_MAX_SCANS_PER_RUN=1)

        self.assertEqual(result["queued"], 1)
        self.assertEqual(
            Scan.objects.filter(trigger=Scan.Trigger.MONITORING).count(), 1
        )


class MonitoringAccessTests(APITestCase):
    def setUp(self) -> None:
        self.owner, self.organization, self.website = self._tenant(
            "mon-owner@example.com", "mon-owner.example"
        )
        self.viewer = User.objects.create_user(
            email="mon-viewer@example.com", password="pass1234!"
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.viewer,
            role=Membership.Role.VIEWER,
        )
        self.outsider, _org, _website = self._tenant(
            "mon-outsider@example.com", "mon-outsider.example"
        )
        self.detail_url = reverse(
            "monitoring-detail", kwargs={"website_id": self.website.pk}
        )
        self.scan_url = reverse(
            "monitoring-trigger-scan", kwargs={"website_id": self.website.pk}
        )

    @staticmethod
    def _tenant(email: str, domain: str):
        user = User.objects.create_user(email=email, password="pass1234!")
        website = Website.objects.create(owner=user, domain=domain)
        return user, website.organization, website

    def test_owner_can_change_the_scan_policy(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            self.detail_url, {"scan_type": "security"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["scan_type"], "security")
        self.assertEqual(
            MonitoringConfig.objects.get(website=self.website).scan_type,
            MonitoringConfig.ScanPolicy.SECURITY,
        )

    def test_invalid_scan_policy_is_rejected(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            self.detail_url, {"scan_type": "everything"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_viewer_cannot_change_the_policy(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.patch(
            self.detail_url, {"scan_type": "full"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_viewer_can_read_the_policy(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("scan_type", response.data)

    def test_outsider_gets_404(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_manual_trigger_uses_the_requested_scan_type(self):
        self.client.force_authenticate(user=self.owner)
        with patch("scans.tasks.run_authenticated_scan.delay") as delay:
            response = self.client.post(
                self.scan_url, {"scan_type": "security"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        scan = Scan.objects.get(website=self.website)
        self.assertEqual(scan.scan_type, Scan.ScanType.SECURITY)
        delay.assert_called_once_with(scan.pk)

    def test_manual_trigger_defaults_to_the_policy(self):
        config = MonitoringConfig.objects.get(website=self.website)
        config.scan_type = MonitoringConfig.ScanPolicy.FULL
        config.save(update_fields=["scan_type"])

        self.client.force_authenticate(user=self.owner)
        with patch("scans.tasks.run_authenticated_scan.delay"):
            response = self.client.post(self.scan_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            Scan.objects.get(website=self.website).scan_type, Scan.ScanType.FULL
        )

    def test_viewer_cannot_trigger_a_scan(self):
        self.client.force_authenticate(user=self.viewer)
        with patch("scans.tasks.run_authenticated_scan.delay") as delay:
            response = self.client.post(self.scan_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        delay.assert_not_called()
        self.assertEqual(Scan.objects.count(), 0)

    def test_trigger_conflicts_with_an_active_scan(self):
        Scan.objects.create(
            website=self.website,
            scan_type=Scan.ScanType.SECURITY,
            status=Scan.Status.RUNNING,
        )
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self.scan_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(response.data["scan_already_running"])
