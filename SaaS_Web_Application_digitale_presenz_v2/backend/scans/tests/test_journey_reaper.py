"""Tests for the progressive journey reaper (Lot E).

Covers the three maintenance passes, their idempotence, the Celery task and
beat entry, the Redis counters/gauges and the journey coverage alerts.  The
reaper is exercised directly against the database; no broker is required.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from alerts.models import Alert, AlertPreference, MuteWindow
from core.reaper_metrics import (
    JOURNEYS_LAST_TICK_KEY,
    read_reaper_metrics,
    record_journey_reaper_tick,
    record_reaper_tick,
)
from scans.models import JourneyState, Scan, ScanJourney
from scans.services.journey_coverage import (
    ISSUE_ACCUMULATION,
    ISSUE_STUCK_AWAITING,
    ISSUE_STUCK_RUNNING,
    check_journey_coverage,
)
from scans.services.journey_reaper import (
    journey_gauges,
    reap_expired_journeys,
    reap_journeys,
    reap_orphan_journeys,
    reconcile_stale_journeys,
)
from scans.tasks import reap_stale_journeys
from websites.models import Website


class JourneyReaperTestMixin:
    """An owner, a personal organization and one website per test."""

    def setUp(self) -> None:
        cache.clear()
        self.user = User.objects.create_user(
            "journey-reaper@example.com", "CorrectHorseBattery1!"
        )
        self.website = Website.objects.create(
            owner=self.user, domain="journey-reaper.example"
        )

    def _website(self, domain: str) -> Website:
        return Website.objects.create(owner=self.user, domain=domain)

    def _journey(
        self,
        *,
        state: str = JourneyState.RUNNING,
        current_stage: int = 1,
        expires_at=None,
        website: Website | None = None,
        created_at=None,
        updated_at=None,
    ) -> ScanJourney:
        journey = ScanJourney.objects.create(
            website=website or self.website,
            requested_by=self.user,
            state=state,
            current_stage=current_stage,
            total_stages=2,
            expires_at=expires_at,
        )
        updates = {}
        if created_at is not None:
            updates["created_at"] = created_at
        if updated_at is not None:
            updates["updated_at"] = updated_at
        if updates:
            ScanJourney.objects.filter(pk=journey.pk).update(**updates)
            journey.refresh_from_db()
        return journey

    def _stage(
        self,
        journey: ScanJourney,
        *,
        stage: int | None = None,
        status: str = Scan.Status.QUEUED,
    ) -> Scan:
        stage = stage or journey.current_stage
        return Scan.objects.create(
            website=journey.website,
            scan_type=Scan.ScanType.SECURITY,
            status=status,
            journey=journey,
            journey_stage=stage,
            quota_charged=stage == 1,
        )


# ---------------------------------------------------------------------------
# Expiration
# ---------------------------------------------------------------------------


class JourneyExpiryTests(JourneyReaperTestMixin, TestCase):
    def test_expires_awaiting_journey_past_deadline(self) -> None:
        journey = self._journey(
            state=JourneyState.AWAITING_CONFIRMATION,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        self.assertEqual(reap_expired_journeys(), 1)

        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.EXPIRED)
        self.assertIsNotNone(journey.expires_at)

    def test_future_deadline_is_untouched(self) -> None:
        journey = self._journey(
            state=JourneyState.AWAITING_CONFIRMATION,
            expires_at=timezone.now() + timedelta(hours=1),
        )

        self.assertEqual(reap_expired_journeys(), 0)
        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.AWAITING_CONFIRMATION)

    def test_already_expired_is_idempotent(self) -> None:
        journey = self._journey(
            state=JourneyState.EXPIRED,
            expires_at=timezone.now() - timedelta(hours=2),
        )

        self.assertEqual(reap_expired_journeys(), 0)
        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.EXPIRED)

    def test_running_journey_with_past_deadline_is_untouched(self) -> None:
        journey = self._journey(
            state=JourneyState.RUNNING,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        self.assertEqual(reap_expired_journeys(), 0)
        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.RUNNING)

    def test_completed_journey_is_untouched(self) -> None:
        journey = self._journey(
            state=JourneyState.COMPLETED,
            expires_at=timezone.now() - timedelta(days=1),
        )

        self.assertEqual(reap_expired_journeys(), 0)
        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.COMPLETED)

    def test_mixed_batch_expires_only_due_journeys(self) -> None:
        now = timezone.now()
        due = [
            self._journey(
                state=JourneyState.AWAITING_CONFIRMATION,
                expires_at=now - timedelta(minutes=1),
                website=self._website(f"due-{index}.example"),
            )
            for index in range(3)
        ]
        future = [
            self._journey(
                state=JourneyState.AWAITING_CONFIRMATION,
                expires_at=now + timedelta(hours=1),
                website=self._website(f"future-{index}.example"),
            )
            for index in range(2)
        ]

        self.assertEqual(reap_expired_journeys(), 3)

        for journey in due:
            journey.refresh_from_db()
            self.assertEqual(journey.state, JourneyState.EXPIRED)
        for journey in future:
            journey.refresh_from_db()
            self.assertEqual(journey.state, JourneyState.AWAITING_CONFIRMATION)


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


class JourneyReconciliationTests(JourneyReaperTestMixin, TestCase):
    def test_terminal_stage_one_failure_fails_the_journey(self) -> None:
        journey = self._journey()
        self._stage(journey, status=Scan.Status.FAILED)

        self.assertEqual(reconcile_stale_journeys(), 1)

        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.FAILED)

    def test_terminal_stage_one_success_parks_for_confirmation(self) -> None:
        journey = self._journey()
        self._stage(journey, status=Scan.Status.COMPLETED)

        before = timezone.now()
        self.assertEqual(reconcile_stale_journeys(), 1)

        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.AWAITING_CONFIRMATION)
        self.assertIsNotNone(journey.expires_at)
        self.assertGreater(journey.expires_at, before)

    def test_terminal_stage_two_success_completes_the_journey(self) -> None:
        journey = self._journey(current_stage=2)
        self._stage(journey, stage=2, status=Scan.Status.COMPLETED)

        self.assertEqual(reconcile_stale_journeys(), 1)

        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.COMPLETED)

    def test_terminal_stage_two_partial_marks_the_journey_partial(self) -> None:
        journey = self._journey(current_stage=2)
        self._stage(journey, stage=2, status=Scan.Status.PARTIAL)

        self.assertEqual(reconcile_stale_journeys(), 1)

        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.PARTIAL)

    def test_active_child_scan_is_not_reconciled(self) -> None:
        journey = self._journey()
        self._stage(journey, status=Scan.Status.RUNNING)

        self.assertEqual(reconcile_stale_journeys(), 0)

        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.RUNNING)

    def test_queued_child_scan_is_not_reconciled(self) -> None:
        journey = self._journey()
        self._stage(journey, status=Scan.Status.QUEUED)

        self.assertEqual(reconcile_stale_journeys(), 0)

        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.RUNNING)

    def test_missing_child_is_logged_and_untouched(self) -> None:
        journey = self._journey()

        with self.assertLogs(
            "scans.services.journey_reaper", level="WARNING"
        ) as captured:
            self.assertEqual(reconcile_stale_journeys(), 0)

        self.assertTrue(
            any("journey_reaper_no_child" in line for line in captured.output)
        )
        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.RUNNING)

    def test_second_run_is_idempotent(self) -> None:
        journey = self._journey()
        self._stage(journey, status=Scan.Status.FAILED)

        self.assertEqual(reconcile_stale_journeys(), 1)
        self.assertEqual(reconcile_stale_journeys(), 0)

        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.FAILED)


# ---------------------------------------------------------------------------
# Orphans
# ---------------------------------------------------------------------------


@override_settings(SCAN_JOURNEY_TTL_HOURS=24)
class JourneyOrphanTests(JourneyReaperTestMixin, TestCase):
    def test_old_running_journey_without_scan_is_failed(self) -> None:
        journey = self._journey(
            created_at=timezone.now() - timedelta(hours=25),
        )

        self.assertEqual(reap_orphan_journeys(), 1)

        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.FAILED)
        self.assertIsNone(journey.expires_at)

    def test_recent_running_journey_is_untouched(self) -> None:
        journey = self._journey(
            created_at=timezone.now() - timedelta(hours=1),
        )

        self.assertEqual(reap_orphan_journeys(), 0)

        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.RUNNING)

    def test_old_running_journey_with_active_scan_is_untouched(self) -> None:
        journey = self._journey(
            created_at=timezone.now() - timedelta(hours=25),
        )
        self._stage(journey, status=Scan.Status.RUNNING)

        self.assertEqual(reap_orphan_journeys(), 0)

        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.RUNNING)

    def test_old_running_journey_with_terminal_scan_is_failed(self) -> None:
        journey = self._journey(
            created_at=timezone.now() - timedelta(hours=25),
        )
        self._stage(journey, status=Scan.Status.COMPLETED)

        self.assertEqual(reap_orphan_journeys(), 1)

        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.FAILED)


# ---------------------------------------------------------------------------
# Full sweep and Celery task
# ---------------------------------------------------------------------------


class FullJourneyReaperTests(JourneyReaperTestMixin, TestCase):
    def test_full_sweep_runs_every_pass_and_records_metrics(self) -> None:
        self._journey(
            state=JourneyState.AWAITING_CONFIRMATION,
            expires_at=timezone.now() - timedelta(minutes=1),
            website=self._website("expired.example"),
        )
        running = self._journey(website=self._website("reconciled.example"))
        self._stage(running, status=Scan.Status.FAILED)

        result = reap_journeys()

        self.assertEqual(result["expired"], 1)
        self.assertEqual(result["reconciled"], 1)
        self.assertEqual(result["orphans"], 0)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["active"], 0)
        self.assertEqual(result["awaiting"], 0)

        metrics = read_reaper_metrics()
        self.assertEqual(metrics["journeys_total"], 2)
        self.assertEqual(metrics["journeys_expired_total"], 1)
        self.assertEqual(metrics["journeys_reconciled_total"], 1)
        self.assertEqual(metrics["journeys_orphans_total"], 0)
        self.assertEqual(metrics["journeys_active_count"], 0)
        self.assertEqual(metrics["journeys_awaiting_count"], 0)
        self.assertIsNotNone(metrics["journeys_last_tick"])
        self.assertEqual(metrics["last_tick"], metrics["journeys_last_tick"])

    def test_second_sweep_changes_nothing(self) -> None:
        self._journey(
            state=JourneyState.AWAITING_CONFIRMATION,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        first = reap_journeys()
        second = reap_journeys()

        self.assertEqual(first["total"], 1)
        self.assertEqual(second["total"], 0)
        self.assertEqual(read_reaper_metrics()["journeys_total"], 1)

    def test_gauges_count_active_and_awaiting_journeys(self) -> None:
        self._journey(
            state=JourneyState.AWAITING_CONFIRMATION,
            expires_at=timezone.now() + timedelta(hours=1),
            website=self._website("awaiting.example"),
        )
        self._journey(
            state=JourneyState.RUNNING,
            website=self._website("running.example"),
        )
        self._journey(
            state=JourneyState.COMPLETED,
            website=self._website("completed.example"),
        )

        self.assertEqual(journey_gauges(), {"active": 2, "awaiting": 1})


class ReapStaleJourneysTaskTests(JourneyReaperTestMixin, TestCase):
    def test_task_returns_the_reaper_metrics(self) -> None:
        self._journey(
            state=JourneyState.AWAITING_CONFIRMATION,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        result = reap_stale_journeys.apply().get()

        self.assertEqual(result["expired"], 1)
        self.assertEqual(result["total"], 1)


class BeatScheduleTests(SimpleTestCase):
    def test_journey_reaper_is_scheduled_every_five_minutes(self) -> None:
        entry = settings.CELERY_BEAT_SCHEDULE["reap-stale-journeys"]

        self.assertEqual(entry["task"], "scans.tasks.reap_stale_journeys")
        self.assertEqual(entry["schedule"], 300.0)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class JourneyReaperMetricsTests(TestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_journeys_kind_is_accepted(self) -> None:
        record_reaper_tick(kind="journeys", reaped=2)

        metrics = read_reaper_metrics()
        self.assertEqual(metrics["journeys_total"], 2)
        self.assertIsNotNone(metrics["journeys_last_tick"])
        self.assertEqual(metrics["last_tick"], metrics["journeys_last_tick"])

    def test_unknown_kind_is_still_rejected(self) -> None:
        with self.assertRaises(ValueError):
            record_reaper_tick(kind="unknown", reaped=1)

    def test_breakdown_and_gauges_are_recorded(self) -> None:
        record_journey_reaper_tick(
            expired=1,
            reconciled=2,
            orphans=3,
            active=4,
            awaiting=5,
        )

        metrics = read_reaper_metrics()
        self.assertEqual(metrics["journeys_total"], 6)
        self.assertEqual(metrics["journeys_expired_total"], 1)
        self.assertEqual(metrics["journeys_reconciled_total"], 2)
        self.assertEqual(metrics["journeys_orphans_total"], 3)
        self.assertEqual(metrics["journeys_active_count"], 4)
        self.assertEqual(metrics["journeys_awaiting_count"], 5)

    def test_counters_accumulate_across_ticks(self) -> None:
        record_journey_reaper_tick(expired=1, active=2, awaiting=1)
        record_journey_reaper_tick(expired=2, reconciled=1, active=3, awaiting=1)

        metrics = read_reaper_metrics()
        self.assertEqual(metrics["journeys_total"], 4)
        self.assertEqual(metrics["journeys_expired_total"], 3)
        self.assertEqual(metrics["journeys_reconciled_total"], 1)
        self.assertEqual(metrics["journeys_active_count"], 3)
        self.assertEqual(metrics["journeys_awaiting_count"], 1)


# ---------------------------------------------------------------------------
# Coverage alerts
# ---------------------------------------------------------------------------


class JourneyCoverageTests(JourneyReaperTestMixin, TestCase):
    def _stuck_awaiting(self, *, hours: int = 13) -> ScanJourney:
        return self._journey(
            state=JourneyState.AWAITING_CONFIRMATION,
            expires_at=timezone.now() + timedelta(hours=11),
            updated_at=timezone.now() - timedelta(hours=hours),
        )

    def test_stuck_awaiting_creates_a_warning_alert(self) -> None:
        journey = self._stuck_awaiting()

        result = check_journey_coverage()

        self.assertEqual(result["alerts_created"], 1)
        alert = Alert.objects.get(website=self.website)
        self.assertEqual(alert.alert_type, Alert.AlertType.SCAN_FAILED)
        self.assertEqual(alert.severity, Alert.Severity.WARNING)
        self.assertEqual(alert.metadata["kind"], "journeys")
        self.assertEqual(alert.metadata["issue"], ISSUE_STUCK_AWAITING)
        self.assertEqual(alert.metadata["journey_id"], journey.pk)
        self.assertIsNone(alert.scan)

    def test_recent_awaiting_does_not_alert(self) -> None:
        self._stuck_awaiting(hours=2)

        result = check_journey_coverage()

        self.assertEqual(result["alerts_created"], 0)
        self.assertFalse(Alert.objects.exists())

    def test_stuck_running_creates_an_alert(self) -> None:
        journey = self._journey(
            updated_at=timezone.now() - timedelta(hours=2),
        )
        self._stage(journey, status=Scan.Status.QUEUED)

        result = check_journey_coverage()

        self.assertEqual(result["alerts_created"], 1)
        alert = Alert.objects.get(website=self.website)
        self.assertEqual(alert.metadata["issue"], ISSUE_STUCK_RUNNING)

    @override_settings(SCAN_JOURNEY_ACCUMULATION_THRESHOLD=0)
    def test_accumulation_alert_uses_a_website_threshold(self) -> None:
        journey = self._journey(
            state=JourneyState.AWAITING_CONFIRMATION,
            expires_at=timezone.now() + timedelta(hours=23),
            updated_at=timezone.now(),
        )

        result = check_journey_coverage()

        self.assertEqual(result["alerts_created"], 1)
        alert = Alert.objects.get(website=self.website)
        self.assertEqual(alert.metadata["issue"], ISSUE_ACCUMULATION)
        self.assertEqual(alert.metadata["count"], 1)
        self.assertEqual(alert.metadata["journey_id"], journey.pk)

    def test_alerts_are_deduplicated(self) -> None:
        self._stuck_awaiting()

        first = check_journey_coverage()
        second = check_journey_coverage()

        self.assertEqual(first["alerts_created"], 1)
        self.assertEqual(second["alerts_created"], 0)
        self.assertEqual(Alert.objects.count(), 1)

    def test_disabled_preference_skips_the_alert(self) -> None:
        preferences, _ = AlertPreference.objects.get_or_create(user=self.user)
        preferences.scan_failed_enabled = False
        preferences.save(update_fields=["scan_failed_enabled"])

        self._stuck_awaiting()

        self.assertEqual(check_journey_coverage()["alerts_created"], 0)
        self.assertFalse(Alert.objects.exists())

    def test_active_mute_window_skips_the_alert(self) -> None:
        now = timezone.now()
        mute = MuteWindow.objects.create(
            user=self.user,
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=1),
        )
        mute.websites.add(self.website)

        self._stuck_awaiting()

        self.assertEqual(check_journey_coverage()["alerts_created"], 0)
        self.assertFalse(Alert.objects.exists())

    def test_reaper_inactive_is_logged_as_critical(self) -> None:
        cache.set(
            JOURNEYS_LAST_TICK_KEY,
            (timezone.now() - timedelta(minutes=20)).isoformat(),
            timeout=None,
        )

        with self.assertLogs(
            "scans.services.journey_coverage", level="CRITICAL"
        ) as captured:
            result = check_journey_coverage()

        self.assertTrue(result["reaper_inactive"])
        self.assertTrue(
            any("journey_reaper_inactive" in line for line in captured.output)
        )

    def test_missing_previous_tick_is_not_inactive(self) -> None:
        cache.delete(JOURNEYS_LAST_TICK_KEY)

        result = check_journey_coverage()

        self.assertFalse(result["reaper_inactive"])
