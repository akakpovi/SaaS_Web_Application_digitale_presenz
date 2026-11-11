"""A crashed worker must not leave an AI run 'running' forever."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from advisory.models import AIRecommendationRun
from advisory.tasks import _terminal_status, reap_stale_ai_runs
from scans.models import Scan
from websites.models import Website


class StaleAIRunReaperTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="reaper-ai@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(
            owner=self.user, domain="reaper-ai.example"
        )
        self.scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.COMPLETED,
            health_score=40,
        )

    def _run(self, status: str, minutes_old: int = 0) -> AIRecommendationRun:
        run = AIRecommendationRun.objects.create(
            scan=self.scan,
            input_hash="a" * 64,
            status=status,
            attempts=1,
        )
        if minutes_old:
            AIRecommendationRun.objects.filter(pk=run.pk).update(
                updated_at=timezone.now() - timedelta(minutes=minutes_old)
            )
        return run

    @override_settings(AI_ADVISOR_STALE_RUN_SECONDS=600)
    def test_stale_running_run_is_failed_with_an_explicit_code(self) -> None:
        run = self._run(AIRecommendationRun.Status.RUNNING, minutes_old=11)

        result = reap_stale_ai_runs.apply().get()

        run.refresh_from_db()
        self.assertEqual(run.status, AIRecommendationRun.Status.FAILED)
        self.assertEqual(run.error_code, "stale_run_reaped")
        self.assertIsNotNone(run.completed_at)
        self.assertEqual(result["reaped"], 1)
        self.assertEqual(result["run_ids"], [str(run.pk)])

    @override_settings(AI_ADVISOR_STALE_RUN_SECONDS=600)
    def test_fresh_running_run_is_left_alone(self) -> None:
        run = self._run(AIRecommendationRun.Status.RUNNING, minutes_old=2)

        result = reap_stale_ai_runs.apply().get()

        run.refresh_from_db()
        self.assertEqual(run.status, AIRecommendationRun.Status.RUNNING)
        self.assertEqual(result["reaped"], 0)

    @override_settings(AI_ADVISOR_STALE_RUN_SECONDS=600)
    def test_stale_pending_run_is_also_failed(self) -> None:
        run = self._run(AIRecommendationRun.Status.PENDING, minutes_old=30)

        reap_stale_ai_runs.apply().get()

        run.refresh_from_db()
        self.assertEqual(run.status, AIRecommendationRun.Status.FAILED)
        self.assertEqual(run.error_code, "stale_run_reaped")

    @override_settings(AI_ADVISOR_STALE_RUN_SECONDS=60)
    def test_configurable_threshold_is_honoured_with_a_floor(self) -> None:
        run = self._run(AIRecommendationRun.Status.RUNNING, minutes_old=3)

        result = reap_stale_ai_runs.apply().get()

        # The helper floors the window at 60 s, so a 3-minute-old row is stale.
        run.refresh_from_db()
        self.assertEqual(run.status, AIRecommendationRun.Status.FAILED)
        self.assertEqual(result["reaped"], 1)

    def test_reaper_is_scheduled_in_beat(self) -> None:
        entry = settings.CELERY_BEAT_SCHEDULE["reap-stale-ai-runs"]
        self.assertEqual(entry["task"], "advisory.tasks.reap_stale_ai_runs")
        self.assertEqual(entry["schedule"], 300.0)

    def test_terminal_labels_reflect_the_cause(self) -> None:
        self.assertEqual(
            _terminal_status("rate_limit_exceeded"), "failed_quota_exhausted"
        )
        self.assertEqual(
            _terminal_status("guest_quota_exceeded"), "failed_quota_exhausted"
        )
        self.assertEqual(_terminal_status("invalid_api_key"), "failed_configuration")
        self.assertEqual(_terminal_status("client_unavailable"), "failed_configuration")
        self.assertEqual(_terminal_status("AkaServerError"), "failed_upstream_error")

    @override_settings(AI_ADVISOR_STALE_RUN_SECONDS=600)
    @patch("alerts.tasks.report_ai_run_reaped.delay")
    def test_reaped_run_queues_the_operator_alert(self, delay) -> None:
        run = self._run(AIRecommendationRun.Status.RUNNING, minutes_old=11)

        result = reap_stale_ai_runs.apply().get()

        delay.assert_called_once_with(str(run.pk))
        self.assertEqual(result["alerts_queued"], 1)

    @override_settings(AI_ADVISOR_STALE_RUN_SECONDS=600)
    @patch("alerts.tasks.report_ai_run_reaped.delay")
    def test_fresh_run_does_not_queue_an_alert(self, delay) -> None:
        self._run(AIRecommendationRun.Status.RUNNING, minutes_old=2)

        result = reap_stale_ai_runs.apply().get()

        delay.assert_not_called()
        self.assertEqual(result["alerts_queued"], 0)

    @override_settings(AI_ADVISOR_STALE_RUN_SECONDS=600)
    def test_reaped_run_is_visible_as_an_ai_run_reaped_alert(self) -> None:
        from alerts.models import Alert
        from alerts.tasks import report_ai_run_reaped

        run = self._run(AIRecommendationRun.Status.RUNNING, minutes_old=11)
        reap_stale_ai_runs.apply().get()

        # The reaper only queues the task; running it here proves the queued
        # alert actually materialises in the same table operators watch.
        result = report_ai_run_reaped.apply(args=[str(run.pk)]).get()

        self.assertEqual(result["created"], 1)
        alert = Alert.objects.get(pk=result["alert_id"])
        self.assertEqual(alert.alert_type, Alert.AlertType.AI_RUN_REAPED)
        self.assertEqual(alert.status, Alert.Status.FIRING)
        self.assertEqual(alert.website_id, self.website.pk)
        self.assertEqual(alert.metadata["run_id"], str(run.pk))

    @override_settings(AI_ADVISOR_STALE_RUN_SECONDS=600)
    def test_metrics_count_reaped_runs_and_stamp_the_tick(self) -> None:
        from core.reaper_metrics import read_reaper_metrics

        cache.clear()
        self._run(AIRecommendationRun.Status.RUNNING, minutes_old=11)

        reap_stale_ai_runs.apply().get()

        metrics = read_reaper_metrics()
        self.assertEqual(metrics["ai_runs_total"], 1)
        self.assertIsNotNone(metrics["ai_last_tick"])
        self.assertEqual(metrics["last_tick"], metrics["ai_last_tick"])
