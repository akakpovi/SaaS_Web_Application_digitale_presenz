"""Integration tests for the GDPR endpoints on ``/api/v1/auth/``.

Covers:
* ``GET  /api/v1/auth/export/`` — Art. 15 access / Art. 20 portability
* ``DELETE /api/v1/auth/me/``   — Art. 17 erasure (cascade + analytics orphans)

Both endpoints are exercised through the real HTTP surface (DRF test client),
against the real database, so a missing cascade shows up here rather than in
production.
"""

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from alerts.models import Alert, AlertPreference, AlertRule, MuteWindow
from analytics.models import AnalyticsEvent, TrafficLog
from monitoring.models import MonitoringConfig
from notifications.models import NotificationChannel, WebPushSubscription
from public_checker.models import PublicLead
from scans.models import CheckResult, Finding, Scan, ScannerRun
from websites.models import Website


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class GDPRAccountAPITests(APITestCase):
    password = "CorrectHorseBattery1!"

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="maria@example.com",
            password=self.password,
            full_name="Maria Schmidt",
        )
        self.website = Website.objects.create(owner=self.user, domain="example.de")
        self.scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.COMPLETED,
            trigger=Scan.Trigger.MANUAL,
            health_score=78,
        )
        self.check_result = CheckResult.objects.create(
            scan=self.scan,
            category=CheckResult.Category.SSL,
            status="warning",
            score=12,
            summary="Certificate expires in 12 days.",
        )
        self.scanner_run = ScannerRun.objects.create(
            scan=self.scan, scanner="ssl", status=ScannerRun.Status.COMPLETED
        )
        self.finding = Finding.objects.create(
            scanner_run=self.scanner_run,
            category="ssl",
            check_code="ssl.expiry",
            title="Certificate expiring soon",
            severity=Finding.Severity.HIGH,
            status=Finding.Status.WARNING,
        )
        self.alert = Alert.objects.create(
            user=self.user,
            website=self.website,
            scan=self.scan,
            alert_type=Alert.AlertType.SSL_EXPIRING,
            severity=Alert.Severity.WARNING,
            title="SSL certificate expiring",
            message="Expires in 12 days.",
        )
        # MonitoringConfig is auto-created by a post_save signal on Website.
        self.assertTrue(MonitoringConfig.objects.filter(website=self.website).exists())
        self.analytics_event = AnalyticsEvent.objects.create(
            user=self.user, event_type=AnalyticsEvent.EventType.LOGIN
        )
        self.traffic_log = TrafficLog.objects.create(user=self.user, path="/app/dashboard")
        self.authenticate(self.user)

    def authenticate(self, user: User) -> None:
        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # ------------------------------------------------------------------
    # Authentication / authorisation
    # ------------------------------------------------------------------

    def test_export_requires_authentication(self) -> None:
        self.client.credentials()
        response = self.client.get("/api/v1/auth/export/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_requires_authentication(self) -> None:
        self.client.credentials()
        response = self.client.delete("/api/v1/auth/me/", {"password": self.password}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    # ------------------------------------------------------------------
    # Export (Art. 15 / 20)
    # ------------------------------------------------------------------

    def test_export_contains_every_user_owned_dataset(self) -> None:
        response = self.client.get("/api/v1/auth/export/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()

        self.assertEqual(payload["account"]["email"], "maria@example.com")
        self.assertEqual(payload["export_metadata"]["subject_user_id"], self.user.pk)

        self.assertEqual([w["domain"] for w in payload["websites"]], ["example.de"])
        self.assertEqual(len(payload["scans"]), 1)
        self.assertEqual(payload["scans"][0]["id"], self.scan.pk)
        self.assertEqual(len(payload["check_results"]), 1)
        self.assertEqual(len(payload["scanner_runs"]), 1)
        self.assertEqual([f["title"] for f in payload["findings"]], ["Certificate expiring soon"])
        self.assertEqual(len(payload["alerts"]), 1)
        self.assertEqual(len(payload["monitoring_configs"]), 1)
        self.assertTrue(payload["alert_preferences"])
        self.assertTrue(payload["notification_channels"])
        self.assertEqual(payload["record_counts"]["websites"], 1)
        self.assertEqual(payload["record_counts"]["findings"], 1)

        # Datetimes must be JSON-safe (no Python repr leaking into the dump).
        self.assertIn("date_joined", payload["account"])
        self.assertIsInstance(payload["account"]["date_joined"], str)

    def test_export_never_leaks_credentials_or_other_users(self) -> None:
        other = User.objects.create_user(email="other@example.com", password=self.password)
        Website.objects.create(owner=other, domain="other-site.com")
        Alert.objects.create(
            user=other,
            website=Website.objects.get(owner=other),
            alert_type=Alert.AlertType.DNS_PROBLEM,
            severity=Alert.Severity.CRITICAL,
            title="Other user alert",
            message="Not Maria's business.",
        )

        response = self.client.get("/api/v1/auth/export/")
        payload = response.json()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("password", payload["account"])
        self.assertEqual([w["domain"] for w in payload["websites"]], ["example.de"])
        self.assertEqual([a["title"] for a in payload["alerts"]], ["SSL certificate expiring"])

        body = response.content.decode("utf-8")
        self.assertNotIn("other@example.com", body)
        self.assertNotIn("other-site.com", body)

    def test_export_is_not_cacheable(self) -> None:
        response = self.client.get("/api/v1/auth/export/")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIn("attachment", response["Content-Disposition"])

    # ------------------------------------------------------------------
    # Erasure (Art. 17)
    # ------------------------------------------------------------------

    def test_delete_without_password_is_rejected(self) -> None:
        response = self.client.delete("/api/v1/auth/me/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_delete_with_wrong_password_is_rejected(self) -> None:
        response = self.client.delete(
            "/api/v1/auth/me/", {"password": "not-my-password"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(Website.objects.filter(pk=self.website.pk).exists())

    def test_delete_erases_account_and_cascades_every_dataset(self) -> None:
        user_id = self.user.pk
        website_id = self.website.pk
        scan_id = self.scan.pk
        finding_id = self.finding.pk
        alert_id = self.alert.pk
        analytics_id = self.analytics_event.pk
        traffic_id = self.traffic_log.pk

        response = self.client.delete(
            "/api/v1/auth/me/", {"password": self.password}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertGreater(body["deleted"]["account"], 0)

        self.assertFalse(User.objects.filter(pk=user_id).exists())
        self.assertFalse(Website.objects.filter(pk=website_id).exists())
        self.assertFalse(Scan.objects.filter(pk=scan_id).exists())
        self.assertFalse(CheckResult.objects.filter(scan_id=scan_id).exists())
        self.assertFalse(ScannerRun.objects.filter(scan_id=scan_id).exists())
        self.assertFalse(Finding.objects.filter(pk=finding_id).exists())
        self.assertFalse(Alert.objects.filter(pk=alert_id).exists())
        self.assertFalse(MonitoringConfig.objects.filter(website_id=website_id).exists())
        self.assertFalse(NotificationChannel.objects.filter(user_id=user_id).exists())
        self.assertFalse(AlertPreference.objects.filter(user_id=user_id).exists())
        self.assertFalse(AlertRule.objects.filter(user_id=user_id).exists())
        self.assertFalse(MuteWindow.objects.filter(user_id=user_id).exists())
        self.assertFalse(WebPushSubscription.objects.filter(user_id=user_id).exists())

        # Analytics rows are linked with SET_NULL — they must not survive as
        # pseudonymous leftovers of an erased account.
        self.assertFalse(AnalyticsEvent.objects.filter(pk=analytics_id).exists())
        self.assertFalse(TrafficLog.objects.filter(pk=traffic_id).exists())
        self.assertEqual(body["leftovers_removed"], {})

    def test_delete_also_erases_public_scan_leads(self) -> None:
        """A lead row keeps the visitor's e-mail: erasure must remove it."""
        mine = PublicLead.objects.create(
            email="maria@example.com", url_scanned="example.de", converted_to_user=self.user
        )
        same_address = PublicLead.objects.create(
            email="Maria@Example.com", url_scanned="example.de"
        )
        other = PublicLead.objects.create(email="someone@else.com", url_scanned="x.com")

        self.client.delete("/api/v1/auth/me/", {"password": self.password}, format="json")

        self.assertFalse(PublicLead.objects.filter(pk=mine.pk).exists())
        self.assertFalse(PublicLead.objects.filter(pk=same_address.pk).exists())
        self.assertTrue(PublicLead.objects.filter(pk=other.pk).exists())

    def test_deleted_account_can_no_longer_authenticate(self) -> None:
        self.client.delete("/api/v1/auth/me/", {"password": self.password}, format="json")

        self.client.credentials()
        login = self.client.post(
            "/api/v1/auth/login/",
            {"email": "maria@example.com", "password": self.password},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_only_affects_the_calling_account(self) -> None:
        survivor = User.objects.create_user(email="survivor@example.com", password=self.password)
        Website.objects.create(owner=survivor, domain="survivor.com")

        self.client.delete("/api/v1/auth/me/", {"password": self.password}, format="json")

        self.assertFalse(User.objects.filter(email="maria@example.com").exists())
        self.assertTrue(User.objects.filter(email="survivor@example.com").exists())
        self.assertTrue(Website.objects.filter(owner=survivor, domain="survivor.com").exists())
