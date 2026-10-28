"""Alerts must resolve when the underlying problem disappears.

The engine raised alerts for failing checks but never closed them: an SSL
alert, a missing-header alert or a "scan failed" alert stayed ``firing``
forever, so the dashboard accumulated stale incidents and users were paged
for problems that had already been fixed.  These tests lock the resolution
rules and the "never resolve from an incomplete scan" guard.
"""

from unittest import mock

from django.test import TestCase, override_settings

from accounts.models import User
from alerts.models import Alert
from alerts.tasks import detect_alerts
from scans.models import CheckResult, Scan
from websites.models import Website


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AlertAutoResolutionTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="resolve@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(owner=self.user, domain="resolve-example.de")

    def _scan(self, status: Scan.Status = Scan.Status.COMPLETED) -> Scan:
        return Scan.objects.create(
            website=self.website,
            status=status,
            trigger=Scan.Trigger.MONITORING,
            health_score=80,
        )

    def _alert(self, alert_type: str, severity: str = Alert.Severity.WARNING) -> Alert:
        return Alert.objects.create(
            user=self.user,
            website=self.website,
            alert_type=alert_type,
            severity=severity,
            title="Existing incident",
            message="Raised by a previous scan.",
        )

    def _check(self, scan: Scan, category: str, status: str = "healthy") -> CheckResult:
        return CheckResult.objects.create(
            scan=scan,
            category=category,
            status=status,
            score=20,
            summary="ok",
        )

    def test_scan_failed_alert_resolves_after_a_successful_scan(self) -> None:
        alert = self._alert(Alert.AlertType.SCAN_FAILED, Alert.Severity.CRITICAL)
        scan = self._scan()
        self._check(scan, CheckResult.Category.SSL)

        detect_alerts.apply(args=[scan.pk]).get()

        alert.refresh_from_db()
        self.assertEqual(alert.status, Alert.Status.RESOLVED)
        self.assertIsNotNone(alert.resolved_at)

    def test_missing_security_headers_alert_resolves(self) -> None:
        alert = self._alert(Alert.AlertType.SECURITY_HEADERS)
        scan = self._scan()
        self._check(scan, CheckResult.Category.SECURITY_HEADERS, "healthy")
        self._check(scan, CheckResult.Category.SSL)

        detect_alerts.apply(args=[scan.pk]).get()

        alert.refresh_from_db()
        self.assertEqual(alert.status, Alert.Status.RESOLVED)

    def test_ssl_alert_still_firing_when_the_condition_persists(self) -> None:
        alert = self._alert(Alert.AlertType.SSL_EXPIRING, Alert.Severity.CRITICAL)
        scan = self._scan()
        CheckResult.objects.create(
            scan=scan,
            category=CheckResult.Category.SSL,
            status="critical",
            score=0,
            summary="Certificate expires soon.",
            technical_details={"days_until_expiry": 3, "is_valid": True},
        )

        detect_alerts.apply(args=[scan.pk]).get()

        alert.refresh_from_db()
        self.assertEqual(alert.status, Alert.Status.FIRING)

    def test_performance_alert_resolves_when_nothing_is_flagged(self) -> None:
        alert = self._alert(Alert.AlertType.PERFORMANCE)
        scan = self._scan()
        self._check(scan, CheckResult.Category.PERFORMANCE, "healthy")

        detect_alerts.apply(args=[scan.pk]).get()

        alert.refresh_from_db()
        self.assertEqual(alert.status, Alert.Status.RESOLVED)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class IncompleteScanAlertTests(TestCase):
    """An incomplete scan is not evidence that an incident is over."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="partial-alert@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(owner=self.user, domain="partial-alert.de")

    def test_partial_scan_does_not_create_or_resolve_alerts(self) -> None:
        alert = Alert.objects.create(
            user=self.user,
            website=self.website,
            alert_type=Alert.AlertType.SSL_EXPIRED,
            severity=Alert.Severity.CRITICAL,
            title="SSL expired",
            message="Certificate expired.",
        )
        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.PARTIAL,
            trigger=Scan.Trigger.MONITORING,
            health_score=40,
        )
        CheckResult.objects.create(
            scan=scan,
            category=CheckResult.Category.SSL,
            status="critical",
            score=0,
            summary="Certificate expired.",
        )

        result = detect_alerts.apply(args=[scan.pk]).get()

        self.assertEqual(result, {"skipped": "not_completed"})
        alert.refresh_from_db()
        self.assertEqual(alert.status, Alert.Status.FIRING)
        self.assertEqual(Alert.objects.filter(website=self.website).count(), 1)

    def test_failed_scan_does_not_create_an_ssl_alert(self) -> None:
        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.FAILED,
            trigger=Scan.Trigger.MONITORING,
            failure_message="scanner crashed",
        )
        CheckResult.objects.create(
            scan=scan,
            category=CheckResult.Category.SSL,
            status="critical",
            score=0,
            summary="Certificate expired.",
        )

        detect_alerts.apply(args=[scan.pk]).get()

        self.assertFalse(Alert.objects.filter(website=self.website).exists())
