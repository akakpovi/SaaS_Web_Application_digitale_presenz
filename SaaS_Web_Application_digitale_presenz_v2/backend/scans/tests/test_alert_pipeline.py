"""Tests for the scan → alert → e-mail pipeline.

The alert engine (``alerts.tasks.detect_alerts``) was implemented but never
triggered by the scan pipeline, so ``Alert`` stayed empty and no alert e-mail
was ever sent.  These tests lock in the wiring:

* a COMPLETED scan queues ``detect_alerts``;
* a FAILED scan does not;
* a broker outage while queuing never turns a good scan into a failure;
* ``detect_alerts`` creates the alert and delivers it through the user's
  default e-mail channel.
"""

from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from alerts.models import Alert, MuteWindow
from notifications.models import NotificationChannel
from notifications.signals import ensure_default_email_channel
from scans.models import CheckResult, Scan
from scans.services.orchestrator import ScanOrchestrator
from scans.tasks import _dispatch_alert_detection, run_authenticated_scan
from websites.models import Website


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ScanAlertTriggerTests(TestCase):
    """The scan task must hand every completed scan to the alert engine."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="scan@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(owner=self.user, domain="scan-example.de")
        self.scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.QUEUED,
            trigger=Scan.Trigger.MANUAL,
            scan_type=Scan.ScanType.HEALTH,
        )

    def _patch_orchestrator(self, final_status: Scan.Status, score: int | None = 55):
        """Replace the real orchestrator run with a state transition only."""

        def fake_run(orchestrator_self):
            Scan.objects.filter(pk=orchestrator_self.scan_id).update(
                status=final_status, health_score=score
            )

        return mock.patch.object(ScanOrchestrator, "run", fake_run)

    def test_completed_scan_queues_detect_alerts(self) -> None:
        with (
            self._patch_orchestrator(Scan.Status.COMPLETED),
            mock.patch("alerts.tasks.detect_alerts.delay") as delay,
        ):
            run_authenticated_scan.apply(args=[self.scan.pk]).get()

        delay.assert_called_once_with(self.scan.pk)

    def test_failed_scan_does_not_queue_detect_alerts(self) -> None:
        with (
            self._patch_orchestrator(Scan.Status.FAILED, score=None),
            mock.patch("alerts.tasks.detect_alerts.delay") as delay,
        ):
            run_authenticated_scan.apply(args=[self.scan.pk]).get()

        delay.assert_not_called()

    def test_broker_outage_while_queuing_does_not_fail_the_scan(self) -> None:
        """Alert detection is a side effect: losing the broker must not fail a scan."""
        with mock.patch(
            "alerts.tasks.detect_alerts.delay", side_effect=RuntimeError("broker down")
        ):
            self.assertFalse(_dispatch_alert_detection(self.scan.pk))

    def test_successful_queue_returns_true(self) -> None:
        with mock.patch("alerts.tasks.detect_alerts.delay") as delay:
            self.assertTrue(_dispatch_alert_detection(self.scan.pk))
        delay.assert_called_once_with(self.scan.pk)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class DetectAlertsDeliveryTests(TestCase):
    """``detect_alerts`` must create the alert *and* e-mail it to the owner."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="alert@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(
            owner=self.user, domain="alert-example.de"
        )
        self.scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.COMPLETED,
            trigger=Scan.Trigger.MONITORING,
            health_score=60,
        )
        CheckResult.objects.create(
            scan=self.scan,
            category=CheckResult.Category.SSL,
            status="critical",
            score=0,
            summary="Certificate expires soon.",
            technical_details={"days_until_expiry": 3, "is_valid": True},
        )
        mail.outbox.clear()

    def test_alert_created_and_emailed(self) -> None:
        from alerts.tasks import detect_alerts

        result = detect_alerts.apply(args=[self.scan.pk]).get()

        self.assertEqual(result["created"], 1)

        alert = Alert.objects.get(website=self.website)
        self.assertEqual(alert.alert_type, Alert.AlertType.SSL_EXPIRED)
        self.assertEqual(alert.severity, Alert.Severity.CRITICAL)
        self.assertEqual(alert.status, Alert.Status.FIRING)
        self.assertEqual(alert.scan_id, self.scan.pk)

        self.assertEqual(alert.notification_channels_sent, ["email"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_second_run_does_not_duplicate_a_firing_alert(self) -> None:
        from alerts.tasks import detect_alerts

        detect_alerts.apply(args=[self.scan.pk]).get()
        second = detect_alerts.apply(args=[self.scan.pk]).get()

        self.assertEqual(second["created"], 0)
        self.assertEqual(Alert.objects.filter(website=self.website).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_active_mute_window_suppresses_alerts(self) -> None:
        from alerts.tasks import detect_alerts

        now = timezone.now()
        MuteWindow.objects.create(
            user=self.user,
            start_at=now - timezone.timedelta(hours=1),
            end_at=now + timezone.timedelta(hours=1),
            is_active=True,
        )

        result = detect_alerts.apply(args=[self.scan.pk]).get()

        self.assertEqual(result, {"skipped": "mute_window"})
        self.assertFalse(Alert.objects.filter(website=self.website).exists())
        self.assertEqual(mail.outbox, [])

    def test_default_email_channel_exists_for_the_owner(self) -> None:
        channels = NotificationChannel.objects.filter(user=self.user, enabled=True)
        self.assertEqual(channels.count(), 1)
        channel = channels.get()
        self.assertEqual(channel.channel_type, NotificationChannel.ChannelType.EMAIL)
        self.assertEqual(channel.config["email"], self.user.email)

    def test_default_email_channel_provisioning_is_idempotent(self) -> None:
        self.assertFalse(ensure_default_email_channel(self.user))
        self.assertEqual(
            NotificationChannel.objects.filter(
                user=self.user, channel_type=NotificationChannel.ChannelType.EMAIL
            ).count(),
            1,
        )

    def test_alert_without_channel_delivers_to_nothing_but_still_creates(self) -> None:
        """Disabling every channel stops delivery, not alert creation."""
        NotificationChannel.objects.filter(user=self.user).update(enabled=False)

        from alerts.tasks import detect_alerts

        result = detect_alerts.apply(args=[self.scan.pk]).get()

        self.assertEqual(result["created"], 1)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(
            Alert.objects.get(website=self.website).notification_channels_sent, []
        )
