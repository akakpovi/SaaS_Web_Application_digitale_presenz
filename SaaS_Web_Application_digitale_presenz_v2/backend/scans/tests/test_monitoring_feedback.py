"""Scan outcomes feed the continuous-monitoring counters.

``MonitoringConfig.consecutive_failures`` was never updated by the scan
pipeline: the monitoring page showed 0 failures and the escalation logic could
never fire.  These tests pin the feedback loop and the severity escalation of
the coverage alert.
"""

from django.test import TestCase, override_settings

from accounts.models import User
from alerts.models import Alert
from alerts.tasks import report_scan_issue
from monitoring.models import MonitoringConfig
from scans.models import Scan
from scans.tasks import _finalize_scan
from websites.models import Website


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MonitoringOutcomeFeedbackTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="feedback@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(owner=self.user, domain="feedback.de")
        self.config = MonitoringConfig.objects.get(website=self.website)

    def _scan(self, status: Scan.Status) -> Scan:
        return Scan.objects.create(
            website=self.website,
            status=status,
            trigger=Scan.Trigger.MONITORING,
        )

    def test_completed_scan_resets_the_failure_counter(self) -> None:
        self.config.consecutive_failures = 2
        self.config.escalation_level = 2
        self.config.save()

        _finalize_scan(self._scan(Scan.Status.COMPLETED).pk)

        self.config.refresh_from_db()
        self.assertEqual(self.config.consecutive_failures, 0)
        self.assertEqual(self.config.escalation_level, 0)

    def test_partial_scan_increments_the_failure_counter(self) -> None:
        _finalize_scan(self._scan(Scan.Status.PARTIAL).pk)

        self.config.refresh_from_db()
        self.assertEqual(self.config.consecutive_failures, 1)
        self.assertEqual(self.config.escalation_level, 1)

    def test_partial_scan_after_failed_scan_escalates(self) -> None:
        _finalize_scan(self._scan(Scan.Status.FAILED).pk)
        _finalize_scan(self._scan(Scan.Status.PARTIAL).pk)

        self.config.refresh_from_db()
        self.assertEqual(self.config.consecutive_failures, 2)
        self.assertEqual(self.config.escalation_level, 1)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CoverageAlertEscalationTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="coverage@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(owner=self.user, domain="coverage.de")
        self.config = MonitoringConfig.objects.get(website=self.website)

    def _partial_scan(self) -> Scan:
        return Scan.objects.create(
            website=self.website,
            status=Scan.Status.PARTIAL,
            trigger=Scan.Trigger.MONITORING,
            failure_message="Gobuster timed out",
        )

    def test_first_partial_scan_is_a_warning(self) -> None:
        report_scan_issue.apply(args=[self._partial_scan().pk]).get()

        alert = Alert.objects.get(website=self.website)
        self.assertEqual(alert.severity, Alert.Severity.WARNING)
        self.assertEqual(alert.status, Alert.Status.FIRING)

    def test_repeated_partial_failure_escalates_to_critical(self) -> None:
        self.config.consecutive_failures = 2
        self.config.save()

        report_scan_issue.apply(args=[self._partial_scan().pk]).get()

        alert = Alert.objects.get(website=self.website)
        self.assertEqual(alert.severity, Alert.Severity.CRITICAL)

    def test_second_incomplete_run_does_not_duplicate_the_alert(self) -> None:
        first = self._partial_scan()
        report_scan_issue.apply(args=[first.pk]).get()
        second = self._partial_scan()
        result = report_scan_issue.apply(args=[second.pk]).get()

        self.assertEqual(result["created"], 0)
        self.assertEqual(Alert.objects.filter(website=self.website).count(), 1)
        self.assertEqual(
            Alert.objects.get(website=self.website).scan_id, second.pk
        )
