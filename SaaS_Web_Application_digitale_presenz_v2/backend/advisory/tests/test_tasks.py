from __future__ import annotations

from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

from celery.exceptions import Retry
from django.test import TestCase, override_settings

from accounts.models import User
from advisory.tasks import generate_scan_recommendations_task
from scans.models import Scan
from scans.services.orchestrator import ScanOrchestrator
from scans.tasks import _dispatch_advisor, run_authenticated_scan
from websites.models import Website


def _fake_result(*, should_retry: bool = False) -> SimpleNamespace:
    run = SimpleNamespace(
        id=uuid4(),
        status="succeeded",
        model_used="model-a",
        error_code="",
    )
    return SimpleNamespace(
        run=run,
        recommendations=[],
        used_fallback=False,
        should_retry=should_retry,
        retry_after_seconds=120.0 if should_retry else None,
        error_code="rate_limit_exceeded" if should_retry else "",
    )


class AdvisorTaskTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="task-advisor@example.com",
            password="pass1234!",
        )
        self.website = Website.objects.create(
            owner=self.user,
            domain="task-advisor.example",
        )
        self.scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.COMPLETED,
            health_score=70,
        )

    @override_settings(AI_ADVISOR_ENABLED=False)
    @mock.patch("advisory.services.advisor.generate_recommendations_for_scan")
    def test_disabled_flag_skips_provider(self, generate: mock.Mock) -> None:
        result = generate_scan_recommendations_task.apply(
            args=[self.scan.pk]
        ).get()

        self.assertEqual(result["status"], "disabled")
        generate.assert_not_called()

    @override_settings(AI_ADVISOR_ENABLED=True)
    @mock.patch(
        "advisory.services.advisor.generate_recommendations_for_scan",
        return_value=_fake_result(),
    )
    def test_enabled_task_calls_service(self, generate: mock.Mock) -> None:
        result = generate_scan_recommendations_task.apply(
            args=[self.scan.pk]
        ).get()

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["model_used"], "model-a")
        generate.assert_called_once_with(self.scan.pk, retry_failed=False)

    @override_settings(AI_ADVISOR_ENABLED=True)
    @mock.patch(
        "advisory.services.advisor.generate_recommendations_for_scan",
        side_effect=RuntimeError("provider exploded"),
    )
    def test_service_exception_is_contained(self, generate: mock.Mock) -> None:
        result = generate_scan_recommendations_task.apply(
            args=[self.scan.pk]
        ).get()

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "RuntimeError")
        generate.assert_called_once()

    @override_settings(AI_ADVISOR_ENABLED=True)
    def test_non_completed_scan_is_skipped(self) -> None:
        self.scan.status = Scan.Status.RUNNING
        self.scan.save(update_fields=["status"])

        result = generate_scan_recommendations_task.apply(
            args=[self.scan.pk]
        ).get()

        self.assertEqual(result["status"], "skipped_not_completed")

    @override_settings(AI_ADVISOR_ENABLED=True)
    @mock.patch(
        "advisory.services.advisor.generate_recommendations_for_scan",
        return_value=_fake_result(should_retry=True),
    )
    def test_quota_exhaustion_requests_a_deferred_retry(
        self, generate: mock.Mock
    ) -> None:
        with mock.patch.object(
            generate_scan_recommendations_task,
            "retry",
            side_effect=Retry(),
        ) as retry:
            result = generate_scan_recommendations_task.apply(
                args=[self.scan.pk]
            )

        self.assertEqual(result.state, "RETRY")
        retry.assert_called_once_with(countdown=120)
        generate.assert_called_once_with(self.scan.pk, retry_failed=False)

    @override_settings(AI_ADVISOR_ENABLED=True)
    @mock.patch(
        "advisory.services.advisor.generate_recommendations_for_scan",
        side_effect=RuntimeError("must not run"),
    )
    def test_dispatch_is_swallowed_and_does_not_break_scan(
        self, generate: mock.Mock
    ) -> None:
        with mock.patch.object(ScanOrchestrator, "run") as orchestrator_run:
            orchestrator_run.side_effect = lambda: Scan.objects.filter(
                pk=self.scan.pk
            ).update(status=Scan.Status.COMPLETED, health_score=70)
            with mock.patch(
                "advisory.tasks.generate_scan_recommendations_task.delay",
                side_effect=RuntimeError("broker down"),
            ):
                with mock.patch("alerts.tasks.detect_alerts.delay"):
                    result = run_authenticated_scan.apply(
                        args=[self.scan.pk]
                    ).get()

        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["advisor_queued"])
        self.scan.refresh_from_db()
        self.assertEqual(self.scan.status, Scan.Status.COMPLETED)


class AdvisorDispatchTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="dispatch-advisor@example.com",
            password="pass1234!",
        )
        self.website = Website.objects.create(
            owner=self.user,
            domain="dispatch-advisor.example",
        )
        self.scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.COMPLETED,
        )

    @override_settings(AI_ADVISOR_ENABLED=False)
    def test_disabled_dispatch_does_not_touch_broker(self) -> None:
        with mock.patch(
            "advisory.tasks.generate_scan_recommendations_task.delay"
        ) as delay:
            self.assertFalse(_dispatch_advisor(self.scan.pk))

        delay.assert_not_called()

    @override_settings(AI_ADVISOR_ENABLED=True)
    def test_enabled_dispatch_uses_delay(self) -> None:
        with mock.patch(
            "advisory.tasks.generate_scan_recommendations_task.delay"
        ) as delay:
            self.assertTrue(_dispatch_advisor(self.scan.pk))

        delay.assert_called_once_with(self.scan.pk)

    @override_settings(AI_ADVISOR_ENABLED=True)
    def test_broker_error_returns_false(self) -> None:
        with mock.patch(
            "advisory.tasks.generate_scan_recommendations_task.delay",
            side_effect=RuntimeError("broker down"),
        ):
            self.assertFalse(_dispatch_advisor(self.scan.pk))

    @override_settings(AI_ADVISOR_ENABLED=True)
    def test_completed_scan_queues_advisor(self) -> None:
        with mock.patch.object(ScanOrchestrator, "run") as orchestrator_run:
            orchestrator_run.side_effect = lambda: Scan.objects.filter(
                pk=self.scan.pk
            ).update(status=Scan.Status.COMPLETED, health_score=70)
            with mock.patch("alerts.tasks.detect_alerts.delay"):
                with mock.patch(
                    "advisory.tasks.generate_scan_recommendations_task.delay"
                ) as delay:
                    result = run_authenticated_scan.apply(
                        args=[self.scan.pk]
                    ).get()

        delay.assert_called_once_with(self.scan.pk)
        self.assertTrue(result["advisor_queued"])
