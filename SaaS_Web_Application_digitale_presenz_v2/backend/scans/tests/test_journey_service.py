"""Tests for the progressive journey orchestration (Lot B).

Covers the admission service, the stage state machine, atomic quota
admission, the atomic QUEUED → RUNNING claim and the absence of classic
scan side effects on journey children.

Concurrency tests use ``TransactionTestCase`` so real PostgreSQL row locks
(``SELECT ... FOR UPDATE``) are exercised instead of a single test
transaction.
"""

from __future__ import annotations

import threading
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.db import close_old_connections, connection
from django.test import (
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    override_settings,
)
from django.utils import timezone

from accounts.models import User
from monitoring.models import MonitoringConfig
from organizations.models import Membership
from scans.models import CheckResult, JourneyState, Scan, ScanJourney
from scans.services.exceptions import (
    JourneyConflictError,
    JourneyExpiredError,
    JourneyStateError,
    QuotaExceededError,
)
from scans.services.journey_service import JourneyService, check_write_permission
from scans.services.orchestrator import (
    ScanOrchestrator,
    _budget_settings_for_scan,
    claim_scan,
)
from scans.services.steps_builder import build_initial_steps, get_steps_for_scan
from scans.tasks import run_authenticated_scan
from subscriptions.models import Plan
from subscriptions.services.quotas import scans_used_this_month
from websites.models import Website


def _patch_dispatch(testcase: TestCase) -> mock.Mock:
    """Silence (and observe) the Celery publication of a stage."""
    patcher = mock.patch("scans.tasks.run_authenticated_scan.delay")
    delay = patcher.start()
    testcase.addCleanup(patcher.stop)
    return delay


class JourneyTestMixin:
    """Shared fixtures: an owner, a personal organization and a website."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            "journey-service@example.com", "CorrectHorseBattery1!"
        )
        self.website = Website.objects.create(
            owner=self.user, domain="journey-service.example"
        )
        self.delay = _patch_dispatch(self)

    def _journey(
        self,
        *,
        state: str = JourneyState.RUNNING,
        current_stage: int = 1,
        expires_at=None,
        website: Website | None = None,
    ) -> ScanJourney:
        return ScanJourney.objects.create(
            website=website or self.website,
            requested_by=self.user,
            state=state,
            current_stage=current_stage,
            total_stages=2,
            expires_at=expires_at,
        )

    def _stage_scan(
        self,
        journey: ScanJourney,
        *,
        stage: int | None = None,
        status: str = Scan.Status.QUEUED,
        quota_charged: bool | None = None,
    ) -> Scan:
        stage = stage or journey.current_stage
        if quota_charged is None:
            quota_charged = stage == 1
        return Scan.objects.create(
            website=journey.website,
            scan_type=Scan.ScanType.SECURITY,
            status=status,
            journey=journey,
            journey_stage=stage,
            quota_charged=quota_charged,
        )


# ---------------------------------------------------------------------------
# Step profiles and budgets
# ---------------------------------------------------------------------------


class JourneyStageProfileTests(SimpleTestCase):
    def test_stage_one_runs_certificate_check_then_deep_tls(self) -> None:
        steps = build_initial_steps("security", journey_stage=1)
        self.assertEqual([step["key"] for step in steps], ["ssl", "testssl"])
        self.assertEqual(steps[0]["scanner"], "ssl")
        self.assertEqual(steps[1]["scanner"], "testssl")
        self.assertNotIn("profile", steps[1])

    def test_stage_one_is_independent_from_the_scan_type(self) -> None:
        for scan_type in ("health", "security", "full"):
            steps = build_initial_steps(scan_type, journey_stage=1)
            self.assertEqual([step["key"] for step in steps], ["ssl", "testssl"])

    def test_get_steps_for_scan_selects_stage_one(self) -> None:
        scan = SimpleNamespace(scan_type="full", journey_stage=1)
        self.assertEqual(
            [step["key"] for step in get_steps_for_scan(scan)],
            ["ssl", "testssl"],
        )

    def test_stage_two_is_unchanged(self) -> None:
        steps = build_initial_steps("security", journey_stage=2)
        self.assertEqual([step["key"] for step in steps], ["nuclei", "gobuster"])

    def test_classic_pipeline_is_unchanged(self) -> None:
        steps = build_initial_steps("security", journey_stage=None)
        self.assertIn("nikto", [step["key"] for step in steps])
        self.assertEqual(len(steps), 8)

    def test_stage_budgets_are_isolated(self) -> None:
        self.assertEqual(
            _budget_settings_for_scan(SimpleNamespace(journey_stage=1)),
            ("SCAN_JOURNEY_STAGE1_TIME_BUDGET_SECONDS", 150),
        )
        self.assertEqual(
            _budget_settings_for_scan(SimpleNamespace(journey_stage=2)),
            ("SCAN_JOURNEY_STAGE2_TIME_BUDGET_SECONDS", 360),
        )
        self.assertEqual(
            _budget_settings_for_scan(SimpleNamespace(journey_stage=None)),
            ("SCAN_TOTAL_TIME_BUDGET_SECONDS", 540),
        )


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


class WritePermissionTests(JourneyTestMixin, TestCase):
    def test_owner_can_write(self) -> None:
        self.assertTrue(check_write_permission(self.user, self.website))

    def test_analyst_can_write(self) -> None:
        analyst = User.objects.create_user(
            "journey-analyst@example.com", "CorrectHorseBattery1!"
        )
        Membership.objects.create(
            organization=self.website.organization,
            user=analyst,
            role=Membership.Role.ANALYST,
        )
        self.assertTrue(check_write_permission(analyst, self.website))

    def test_viewer_is_rejected(self) -> None:
        viewer = User.objects.create_user(
            "journey-viewer@example.com", "CorrectHorseBattery1!"
        )
        Membership.objects.create(
            organization=self.website.organization,
            user=viewer,
            role=Membership.Role.VIEWER,
        )
        with self.assertRaises(PermissionError):
            check_write_permission(viewer, self.website)

    def test_outsider_is_rejected(self) -> None:
        outsider = User.objects.create_user(
            "journey-outsider@example.com", "CorrectHorseBattery1!"
        )
        Website.objects.create(owner=outsider, domain="outsider.example")
        with self.assertRaises(PermissionError):
            check_write_permission(outsider, self.website)

    def test_anonymous_is_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            check_write_permission(AnonymousUser(), self.website)

    def test_superuser_is_allowed(self) -> None:
        root = User.objects.create_superuser(
            email="journey-root@example.com", password="CorrectHorseBattery1!"
        )
        self.assertTrue(check_write_permission(root, self.website))


# ---------------------------------------------------------------------------
# create_journey
# ---------------------------------------------------------------------------


class CreateJourneyTests(JourneyTestMixin, TestCase):
    def test_creates_running_journey_and_charged_stage_one(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            journey = JourneyService.create_journey(self.website, self.user)

        self.assertEqual(journey.state, JourneyState.RUNNING)
        self.assertEqual(journey.current_stage, 1)
        self.assertEqual(journey.total_stages, 2)
        self.assertIsNone(journey.expires_at)
        self.assertEqual(journey.requested_by, self.user)

        scan = journey.stages.get()
        self.assertEqual(scan.status, Scan.Status.QUEUED)
        self.assertEqual(scan.journey_stage, 1)
        self.assertEqual(scan.scan_type, Scan.ScanType.SECURITY)
        self.assertEqual(scan.trigger, Scan.Trigger.MANUAL)
        self.assertTrue(scan.quota_charged)
        self.delay.assert_called_once_with(scan.pk)

    def test_task_is_not_published_before_commit(self) -> None:
        JourneyService.create_journey(self.website, self.user)
        self.delay.assert_not_called()

    def test_trigger_source_is_preserved(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            journey = JourneyService.create_journey(
                self.website, self.user, trigger_source="monitoring"
            )
        self.assertEqual(journey.stages.get().trigger, Scan.Trigger.MONITORING)

    def test_second_active_journey_is_rejected(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            JourneyService.create_journey(self.website, self.user)

        with self.assertRaises(JourneyConflictError):
            JourneyService.create_journey(self.website, self.user)

        self.assertEqual(ScanJourney.objects.count(), 1)
        self.assertEqual(Scan.objects.count(), 1)

    def test_double_click_creates_exactly_one_journey(self) -> None:
        results: list[str] = []
        for _ in range(2):
            try:
                JourneyService.create_journey(self.website, self.user)
                results.append("success")
            except JourneyConflictError:
                results.append("conflict")

        self.assertEqual(sorted(results), ["conflict", "success"])
        self.assertEqual(ScanJourney.objects.count(), 1)

    def test_awaiting_journey_also_blocks_creation(self) -> None:
        self._journey(
            state=JourneyState.AWAITING_CONFIRMATION,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        with self.assertRaises(JourneyConflictError):
            JourneyService.create_journey(self.website, self.user)

    def test_finished_journey_does_not_block_creation(self) -> None:
        ScanJourney.objects.create(
            website=self.website,
            requested_by=self.user,
            state=JourneyState.COMPLETED,
            current_stage=2,
            total_stages=2,
        )
        journey = JourneyService.create_journey(self.website, self.user)
        self.assertEqual(journey.state, JourneyState.RUNNING)

    def test_viewer_cannot_create_a_journey(self) -> None:
        viewer = User.objects.create_user(
            "journey-create-viewer@example.com", "CorrectHorseBattery1!"
        )
        Membership.objects.create(
            organization=self.website.organization,
            user=viewer,
            role=Membership.Role.VIEWER,
        )
        with self.assertRaises(PermissionError):
            JourneyService.create_journey(self.website, viewer)
        self.assertEqual(ScanJourney.objects.count(), 0)

    def test_missing_user_cannot_create_a_journey(self) -> None:
        with self.assertRaises(PermissionError):
            JourneyService.create_journey(self.website, None)
        self.assertEqual(ScanJourney.objects.count(), 0)


# ---------------------------------------------------------------------------
# Quota admission
# ---------------------------------------------------------------------------


class JourneyQuotaTests(TestCase):
    def setUp(self) -> None:
        # The plan must exist before the user so the post_save signal creates
        # the Free subscription that carries it.
        self.plan = Plan.objects.create(
            tier=Plan.Tier.FREE, name="Free test", max_scans_per_month=1
        )
        self.user = User.objects.create_user(
            "journey-quota@example.com", "CorrectHorseBattery1!"
        )
        self.website = Website.objects.create(
            owner=self.user, domain="journey-quota.example"
        )
        self.delay = _patch_dispatch(self)

    def test_quota_exceeded_blocks_the_journey(self) -> None:
        Scan.objects.create(website=self.website, quota_charged=True)
        with self.assertRaises(QuotaExceededError):
            JourneyService.create_journey(self.website, self.user)
        self.assertEqual(ScanJourney.objects.count(), 0)

    def test_uncharged_scans_do_not_consume_the_quota(self) -> None:
        Scan.objects.create(website=self.website, quota_charged=False)
        journey = JourneyService.create_journey(self.website, self.user)
        self.assertIsNotNone(journey.pk)

    def test_stage_one_is_charged_and_stage_two_is_free(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            journey = JourneyService.create_journey(self.website, self.user)

        stage_one = journey.stages.get(journey_stage=1)
        self.assertTrue(stage_one.quota_charged)
        self.assertEqual(
            scans_used_this_month(organization=self.website.organization), 1
        )

        journey.state = JourneyState.AWAITING_CONFIRMATION
        journey.expires_at = timezone.now() + timedelta(hours=24)
        journey.save(update_fields=["state", "expires_at"])

        with override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=True):
            with self.captureOnCommitCallbacks(execute=True):
                journey = JourneyService.advance_journey(journey.pk, self.user)

        stage_two = journey.stages.get(journey_stage=2)
        self.assertFalse(stage_two.quota_charged)
        self.assertEqual(
            scans_used_this_month(organization=self.website.organization), 1
        )

    def test_monthly_counter_ignores_uncharged_scans(self) -> None:
        Scan.objects.create(website=self.website, quota_charged=True)
        Scan.objects.create(website=self.website, quota_charged=False)
        self.assertEqual(
            scans_used_this_month(organization=self.website.organization), 1
        )

    def test_no_plan_means_no_ceiling(self) -> None:
        # Without a subscription nor a Free plan row, the existing quota
        # service enforces no ceiling; admission must not invent one.
        from subscriptions.models import Subscription

        Subscription.objects.filter(user=self.user).delete()
        Plan.objects.all().delete()

        journey = JourneyService.create_journey(self.website, self.user)
        self.assertIsNotNone(journey.pk)


# ---------------------------------------------------------------------------
# on_stage_completed
# ---------------------------------------------------------------------------


class StageCompletionTests(JourneyTestMixin, TestCase):
    def _complete(self, journey: ScanJourney, scan: Scan) -> ScanJourney:
        return JourneyService.on_stage_completed(scan.pk)

    def test_stage_one_completed_awaits_confirmation(self) -> None:
        journey = self._journey()
        scan = self._stage_scan(journey, status=Scan.Status.COMPLETED)

        before = timezone.now()
        journey = self._complete(journey, scan)

        self.assertEqual(journey.state, JourneyState.AWAITING_CONFIRMATION)
        self.assertIsNotNone(journey.expires_at)
        self.assertGreaterEqual(
            journey.expires_at, before + timedelta(hours=23, minutes=59)
        )
        self.assertLessEqual(
            journey.expires_at, timezone.now() + timedelta(hours=24, minutes=1)
        )

    def test_stage_one_partial_awaits_confirmation(self) -> None:
        journey = self._journey()
        scan = self._stage_scan(journey, status=Scan.Status.PARTIAL)
        journey = self._complete(journey, scan)
        self.assertEqual(journey.state, JourneyState.AWAITING_CONFIRMATION)
        self.assertIsNotNone(journey.expires_at)

    def test_stage_one_failed_fails_the_journey(self) -> None:
        journey = self._journey()
        scan = self._stage_scan(journey, status=Scan.Status.FAILED)
        journey = self._complete(journey, scan)
        self.assertEqual(journey.state, JourneyState.FAILED)
        self.assertIsNone(journey.expires_at)

    def test_stage_one_cancelled_fails_the_journey(self) -> None:
        journey = self._journey()
        scan = self._stage_scan(journey, status=Scan.Status.CANCELLED)
        journey = self._complete(journey, scan)
        self.assertEqual(journey.state, JourneyState.FAILED)

    def test_stage_two_completed_completes_the_journey(self) -> None:
        journey = self._journey(current_stage=2)
        scan = self._stage_scan(
            journey, stage=2, status=Scan.Status.COMPLETED, quota_charged=False
        )
        journey = self._complete(journey, scan)
        self.assertEqual(journey.state, JourneyState.COMPLETED)
        self.assertIsNone(journey.expires_at)

    def test_stage_two_partial_makes_the_journey_partial(self) -> None:
        journey = self._journey(current_stage=2)
        scan = self._stage_scan(
            journey, stage=2, status=Scan.Status.PARTIAL, quota_charged=False
        )
        journey = self._complete(journey, scan)
        self.assertEqual(journey.state, JourneyState.PARTIAL)

    def test_stage_two_failed_fails_the_journey(self) -> None:
        journey = self._journey(current_stage=2)
        scan = self._stage_scan(
            journey, stage=2, status=Scan.Status.FAILED, quota_charged=False
        )
        journey = self._complete(journey, scan)
        self.assertEqual(journey.state, JourneyState.FAILED)

    def test_stage_two_cancelled_fails_the_journey(self) -> None:
        journey = self._journey(current_stage=2)
        scan = self._stage_scan(
            journey, stage=2, status=Scan.Status.CANCELLED, quota_charged=False
        )
        journey = self._complete(journey, scan)
        self.assertEqual(journey.state, JourneyState.FAILED)

    def test_duplicate_callback_is_idempotent(self) -> None:
        journey = self._journey()
        scan = self._stage_scan(journey, status=Scan.Status.PARTIAL)
        first = self._complete(journey, scan)
        expires = first.expires_at

        second = self._complete(journey, scan)

        self.assertEqual(second.state, JourneyState.AWAITING_CONFIRMATION)
        self.assertEqual(second.expires_at, expires)

    def test_classic_scan_is_ignored(self) -> None:
        scan = Scan.objects.create(website=self.website, status=Scan.Status.COMPLETED)
        self.assertIsNone(JourneyService.on_stage_completed(scan.pk))

    def test_non_terminal_scan_is_ignored(self) -> None:
        journey = self._journey()
        scan = self._stage_scan(journey, status=Scan.Status.RUNNING)
        journey = self._complete(journey, scan)
        self.assertEqual(journey.state, JourneyState.RUNNING)

    def test_stale_stage_callback_is_ignored(self) -> None:
        journey = self._journey(current_stage=2)
        stale = self._stage_scan(journey, stage=1, status=Scan.Status.COMPLETED)
        self._stage_scan(journey, stage=2, status=Scan.Status.RUNNING)

        journey = self._complete(journey, stale)
        self.assertEqual(journey.state, JourneyState.RUNNING)
        self.assertIsNone(journey.expires_at)


# ---------------------------------------------------------------------------
# advance_journey
# ---------------------------------------------------------------------------


class AdvanceJourneyTests(JourneyTestMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.journey = self._journey(
            state=JourneyState.AWAITING_CONFIRMATION,
            current_stage=1,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        self.stage_one = self._stage_scan(
            self.journey, stage=1, status=Scan.Status.COMPLETED
        )

    @override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=True)
    def test_advance_creates_stage_two_without_charging_quota(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            journey = JourneyService.advance_journey(self.journey.pk, self.user)

        self.assertEqual(journey.state, JourneyState.RUNNING)
        self.assertEqual(journey.current_stage, 2)
        self.assertIsNone(journey.expires_at)

        stage_two = journey.stages.get(journey_stage=2)
        self.assertEqual(stage_two.status, Scan.Status.QUEUED)
        self.assertFalse(stage_two.quota_charged)
        self.assertEqual(stage_two.scan_type, Scan.ScanType.SECURITY)
        self.delay.assert_called_once_with(stage_two.pk)

    @override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=True)
    def test_task_is_published_only_after_commit(self) -> None:
        JourneyService.advance_journey(self.journey.pk, self.user)
        self.delay.assert_not_called()

    def test_advance_on_running_journey_is_rejected(self) -> None:
        self.journey.state = JourneyState.RUNNING
        self.journey.expires_at = None
        self.journey.save(update_fields=["state", "expires_at"])
        with self.assertRaises(JourneyStateError):
            JourneyService.advance_journey(self.journey.pk, self.user)
        self.assertFalse(
            Scan.objects.filter(journey=self.journey, journey_stage=2).exists()
        )

    def test_advance_after_expiration_is_rejected(self) -> None:
        self.journey.expires_at = timezone.now() - timedelta(minutes=1)
        self.journey.save(update_fields=["expires_at"])
        with self.assertRaises(JourneyExpiredError):
            JourneyService.advance_journey(self.journey.pk, self.user)

    def test_advance_with_active_classic_scan_is_rejected(self) -> None:
        Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)
        with self.assertRaises(JourneyConflictError):
            JourneyService.advance_journey(self.journey.pk, self.user)

        self.journey.refresh_from_db()
        self.assertEqual(self.journey.state, JourneyState.AWAITING_CONFIRMATION)
        self.assertFalse(
            Scan.objects.filter(journey=self.journey, journey_stage=2).exists()
        )

    def test_advance_accepts_a_finished_classic_scan(self) -> None:
        Scan.objects.create(website=self.website, status=Scan.Status.COMPLETED)
        with override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=True):
            journey = JourneyService.advance_journey(self.journey.pk, self.user)
        self.assertEqual(journey.current_stage, 2)

    def test_viewer_cannot_advance(self) -> None:
        viewer = User.objects.create_user(
            "journey-advance-viewer@example.com", "CorrectHorseBattery1!"
        )
        Membership.objects.create(
            organization=self.website.organization,
            user=viewer,
            role=Membership.Role.VIEWER,
        )
        with self.assertRaises(PermissionError):
            JourneyService.advance_journey(self.journey.pk, viewer)
        self.assertFalse(
            Scan.objects.filter(journey=self.journey, journey_stage=2).exists()
        )

    def test_missing_nuclei_fails_the_journey_without_a_stage_two(self) -> None:
        with override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=False):
            journey = JourneyService.advance_journey(self.journey.pk, self.user)

        self.assertEqual(journey.state, JourneyState.FAILED)
        self.assertEqual(journey.current_stage, 1)
        self.assertFalse(
            Scan.objects.filter(journey=self.journey, journey_stage=2).exists()
        )

    @override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=True)
    def test_second_advance_does_not_create_a_second_stage_two(self) -> None:
        JourneyService.advance_journey(self.journey.pk, self.user)
        with self.assertRaises(JourneyStateError):
            JourneyService.advance_journey(self.journey.pk, self.user)

        self.assertEqual(
            Scan.objects.filter(journey=self.journey, journey_stage=2).count(), 1
        )

    def test_unknown_journey_is_rejected(self) -> None:
        with self.assertRaises(JourneyStateError):
            JourneyService.advance_journey(999_999, self.user)


# ---------------------------------------------------------------------------
# cancel_journey
# ---------------------------------------------------------------------------


class CancelJourneyTests(JourneyTestMixin, TestCase):
    def test_cancel_awaiting_journey_keeps_the_finished_scan(self) -> None:
        journey = self._journey(
            state=JourneyState.AWAITING_CONFIRMATION,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        scan = self._stage_scan(journey, status=Scan.Status.COMPLETED)

        journey = JourneyService.cancel_journey(journey.pk, self.user)

        scan.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.CANCELLED)
        self.assertIsNone(journey.expires_at)
        self.assertEqual(scan.status, Scan.Status.COMPLETED)

    def test_cancel_running_journey_cancels_the_active_child(self) -> None:
        journey = self._journey()
        scan = self._stage_scan(journey, status=Scan.Status.RUNNING)

        journey = JourneyService.cancel_journey(journey.pk, self.user)

        scan.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.CANCELLED)
        self.assertEqual(scan.status, Scan.Status.CANCELLED)
        self.assertIsNotNone(scan.completed_at)

    def test_cancel_finished_journey_is_rejected(self) -> None:
        journey = self._journey(current_stage=2)
        journey.state = JourneyState.COMPLETED
        journey.save(update_fields=["state"])
        with self.assertRaises(JourneyStateError):
            JourneyService.cancel_journey(journey.pk, self.user)

    def test_viewer_cannot_cancel(self) -> None:
        journey = self._journey()
        viewer = User.objects.create_user(
            "journey-cancel-viewer@example.com", "CorrectHorseBattery1!"
        )
        Membership.objects.create(
            organization=self.website.organization,
            user=viewer,
            role=Membership.Role.VIEWER,
        )
        with self.assertRaises(PermissionError):
            JourneyService.cancel_journey(journey.pk, viewer)

    def test_cancel_does_not_refund_the_quota(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            journey = JourneyService.create_journey(self.website, self.user)

        JourneyService.cancel_journey(journey.pk, self.user)

        self.assertEqual(
            scans_used_this_month(organization=self.website.organization), 1
        )


# ---------------------------------------------------------------------------
# Atomic claim
# ---------------------------------------------------------------------------


class ClaimScanTests(JourneyTestMixin, TestCase):
    def test_claim_moves_queued_to_running(self) -> None:
        scan = Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)
        self.assertTrue(claim_scan(scan.pk))
        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.RUNNING)
        self.assertIsNotNone(scan.started_at)

    def test_claim_on_running_returns_false(self) -> None:
        scan = Scan.objects.create(website=self.website, status=Scan.Status.RUNNING)
        self.assertFalse(claim_scan(scan.pk))

    def test_claim_on_cancelled_returns_false(self) -> None:
        scan = Scan.objects.create(website=self.website, status=Scan.Status.CANCELLED)
        self.assertFalse(claim_scan(scan.pk))

    def test_claim_on_missing_scan_returns_false(self) -> None:
        self.assertFalse(claim_scan(999_999))


# ---------------------------------------------------------------------------
# Task integration: journey children have no classic side effects
# ---------------------------------------------------------------------------


class JourneyTaskSideEffectTests(JourneyTestMixin, TestCase):
    def _run_task_ending(self, scan: Scan, status: str) -> dict:
        def fake_run(orchestrator_self):
            Scan.objects.filter(pk=orchestrator_self.scan_id).update(status=status)

        with mock.patch.object(ScanOrchestrator, "run", fake_run):
            with mock.patch("alerts.tasks.detect_alerts.delay") as detect:
                with mock.patch(
                    "advisory.tasks.generate_scan_recommendations_task.delay"
                ) as advisor:
                    with mock.patch("alerts.tasks.report_scan_issue.delay") as coverage:
                        result = run_authenticated_scan.apply(args=[scan.pk]).get()
        self.detect = detect
        self.advisor = advisor
        self.coverage = coverage
        return result

    @override_settings(AI_ADVISOR_ENABLED=True)
    def test_journey_stage_one_triggers_no_classic_side_effect(self) -> None:
        journey = self._journey()
        scan = self._stage_scan(journey, status=Scan.Status.QUEUED)
        CheckResult.objects.create(
            scan=scan, category=CheckResult.Category.SSL, score=15
        )
        config = MonitoringConfig.objects.get(website=self.website)
        config.consecutive_failures = 3
        config.escalation_level = 2
        config.save(update_fields=["consecutive_failures", "escalation_level"])

        result = self._run_task_ending(scan, Scan.Status.COMPLETED)

        self.detect.assert_not_called()
        self.advisor.assert_not_called()
        self.coverage.assert_not_called()
        self.assertEqual(result["journey_state"], JourneyState.AWAITING_CONFIRMATION)

        scan.refresh_from_db()
        config.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.COMPLETED)
        self.assertIsNone(scan.health_score)
        self.assertEqual(config.consecutive_failures, 3)
        self.assertEqual(config.escalation_level, 2)

    @override_settings(AI_ADVISOR_ENABLED=True)
    def test_journey_stage_two_finalises_without_alerts(self) -> None:
        journey = self._journey(current_stage=2)
        scan = self._stage_scan(
            journey, stage=2, status=Scan.Status.QUEUED, quota_charged=False
        )
        config = MonitoringConfig.objects.get(website=self.website)
        config.consecutive_failures = 3
        config.save(update_fields=["consecutive_failures"])

        result = self._run_task_ending(scan, Scan.Status.PARTIAL)

        self.detect.assert_not_called()
        self.advisor.assert_not_called()
        self.coverage.assert_not_called()
        self.assertEqual(result["journey_state"], JourneyState.PARTIAL)

        config.refresh_from_db()
        self.assertEqual(config.consecutive_failures, 3)

    @override_settings(AI_ADVISOR_ENABLED=True)
    def test_classic_scan_keeps_its_side_effects(self) -> None:
        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.QUEUED,
            scan_type=Scan.ScanType.HEALTH,
        )
        config = MonitoringConfig.objects.get(website=self.website)
        config.consecutive_failures = 3
        config.save(update_fields=["consecutive_failures"])

        result = self._run_task_ending(scan, Scan.Status.COMPLETED)

        self.detect.assert_called_once_with(scan.pk)
        self.advisor.assert_called_once_with(scan.pk)
        self.coverage.assert_not_called()
        self.assertEqual(result["status"], Scan.Status.COMPLETED)

        config.refresh_from_db()
        self.assertEqual(config.consecutive_failures, 0)

    def test_classic_queued_scan_is_claimed_before_orchestration(self) -> None:
        scan = Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)

        def fake_run(orchestrator_self):
            Scan.objects.filter(pk=orchestrator_self.scan_id).update(
                status=Scan.Status.COMPLETED
            )

        with mock.patch.object(ScanOrchestrator, "run", fake_run):
            with mock.patch("alerts.tasks.detect_alerts.delay"):
                run_authenticated_scan.apply(args=[scan.pk]).get()

        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.COMPLETED)
        self.assertIsNotNone(scan.started_at)


# ---------------------------------------------------------------------------
# Concurrency (real PostgreSQL row locks)
# ---------------------------------------------------------------------------


class _ConcurrentRunner:
    """Run one callable per thread after a common start barrier."""

    @staticmethod
    def run(targets: list) -> list:
        results: list = []
        barrier = threading.Barrier(len(targets))

        def worker(fn):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                try:
                    results.append(fn())
                except JourneyConflictError:
                    results.append("conflict")
                except JourneyStateError:
                    results.append("state_error")
                except JourneyExpiredError:
                    results.append("expired")
                except QuotaExceededError:
                    results.append("quota")
                except Exception as exc:  # pragma: no cover - diagnostic
                    results.append(f"error:{type(exc).__name__}:{exc}")
            finally:
                # Close the thread-local connection explicitly: a lingering
                # session would keep the test database locked at teardown.
                connection.close()

        threads = [threading.Thread(target=worker, args=(fn,)) for fn in targets]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        if any(thread.is_alive() for thread in threads):
            results.append("error:thread_stuck")
        return results


class ConcurrentJourneyCreationTests(JourneyTestMixin, TransactionTestCase):
    def _create(self, website: Website):
        def call():
            JourneyService.create_journey(website, self.user)
            return "success"

        return call

    def test_two_simultaneous_journeys_on_one_site(self) -> None:
        results = _ConcurrentRunner.run([self._create(self.website)] * 2)

        self.assertEqual(sorted(results), ["conflict", "success"])
        self.assertEqual(ScanJourney.objects.count(), 1)
        self.assertEqual(Scan.objects.count(), 1)

    def test_quota_race_across_two_sites_of_one_organization(self) -> None:
        # A dedicated free plan with a single unit for this test.
        self.user.delete()
        plan = Plan.objects.create(
            tier=Plan.Tier.FREE, name="Free race", max_scans_per_month=1
        )
        user = User.objects.create_user(
            "journey-race@example.com", "CorrectHorseBattery1!"
        )
        self.assertEqual(user.subscription.plan_id, plan.pk)

        website_a = Website.objects.create(owner=user, domain="journey-race-a.example")
        website_b = Website.objects.create(owner=user, domain="journey-race-b.example")
        self.assertEqual(website_a.organization_id, website_b.organization_id)

        def create_for(website):
            def call():
                JourneyService.create_journey(website, user)
                return "success"

            return call

        results = _ConcurrentRunner.run([create_for(website_a), create_for(website_b)])

        self.assertEqual(sorted(results), ["quota", "success"])
        self.assertEqual(ScanJourney.objects.count(), 1)
        self.assertEqual(Scan.objects.filter(quota_charged=True).count(), 1)


@override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=True)
class ConcurrentAdvanceTests(JourneyTestMixin, TransactionTestCase):
    def test_two_simultaneous_advances_create_one_stage_two(self) -> None:
        journey = self._journey(
            state=JourneyState.AWAITING_CONFIRMATION,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        self._stage_scan(journey, stage=1, status=Scan.Status.COMPLETED)

        def advance():
            JourneyService.advance_journey(journey.pk, self.user)
            return "success"

        results = _ConcurrentRunner.run([advance, advance])

        self.assertEqual(sorted(results), ["state_error", "success"])
        self.assertEqual(
            Scan.objects.filter(journey=journey, journey_stage=2).count(), 1
        )


class ConcurrentClaimTests(JourneyTestMixin, TransactionTestCase):
    def test_two_simultaneous_claims_only_one_wins(self) -> None:
        scan = Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)

        def claim():
            return claim_scan(scan.pk)

        results = _ConcurrentRunner.run([claim, claim])

        self.assertEqual(sorted(results), [False, True])
        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.RUNNING)
