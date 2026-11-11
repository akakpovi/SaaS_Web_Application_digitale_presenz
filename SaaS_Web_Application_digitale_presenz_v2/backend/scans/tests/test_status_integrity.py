"""Regression tests for scan-level status aggregation.

The historical bug: a scan whose only Nuclei run timed out was stored as
``completed`` because the orchestrator always transitioned to COMPLETED after
its loop.  These tests lock the outcome to the per-scanner evidence instead.

The cases below cover the contract requested for the status-integrity mission:

* all scanners complete -> completed;
* a required scanner times out/fails while another succeeds -> partial;
* no usable scanner result -> failed;
* optional policy skips do not invalidate a successful scan;
* a partial scan is terminal (a retry cannot turn it into a success);
* the API exposes the partial status and the per-scanner detail;
* ingestion is told a timeout report is incomplete.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from scanners.base import ScanOutcome, ScanResult, ScannerType
from scans.models import Scan, ScannerRun
from scans.services.orchestrator import ScanOrchestrator
from scans.services.status import aggregate_scan_status
from scans.tasks import run_authenticated_scan
from websites.models import Website


def _step(
    name: str,
    status: str,
    *,
    required: bool = True,
    result_usable: bool | None = None,
) -> dict:
    step = {
        "key": name,
        "label": name.title(),
        "scanner": name,
        "weight": 50,
        "required": required,
        "status": status,
        "progress": 100,
        "duration_ms": 1000,
        "error": None,
    }
    if result_usable is not None:
        step["result_usable"] = result_usable
    return step


class AggregateStatusTests(SimpleTestCase):
    def test_all_scanners_completed_is_completed(self) -> None:
        summary = aggregate_scan_status(
            [_step("website", "completed"), _step("ssl", "completed")]
        )
        self.assertEqual(summary.status, Scan.Status.COMPLETED)
        self.assertEqual(summary.reason, "")
        self.assertEqual(summary.incomplete, ())

    def test_one_timeout_with_another_success_is_partial(self) -> None:
        summary = aggregate_scan_status(
            [
                _step("zap", "completed"),
                _step("nuclei", "timeout"),
            ]
        )
        self.assertEqual(summary.status, Scan.Status.PARTIAL)
        self.assertIn("nuclei timeout", summary.reason)
        self.assertEqual(summary.completed, ("zap",))
        self.assertEqual(summary.incomplete, ("nuclei",))

    def test_one_failure_with_another_success_is_partial(self) -> None:
        summary = aggregate_scan_status(
            [
                _step("ssl", "completed"),
                _step("nuclei", "failed", result_usable=False),
            ]
        )
        self.assertEqual(summary.status, Scan.Status.PARTIAL)

    def test_all_scanners_failed_is_failed(self) -> None:
        summary = aggregate_scan_status(
            [
                _step("nuclei", "timeout", result_usable=False),
                _step("zap", "failed", result_usable=False),
            ]
        )
        self.assertEqual(summary.status, Scan.Status.FAILED)
        self.assertIn("no usable scanner result", summary.reason)

    def test_timeout_without_a_stored_result_is_failed(self) -> None:
        summary = aggregate_scan_status(
            [_step("nuclei", "timeout", result_usable=False)]
        )
        self.assertEqual(summary.status, Scan.Status.FAILED)

    def test_optional_policy_skip_does_not_downgrade_success(self) -> None:
        summary = aggregate_scan_status(
            [
                _step("website", "completed"),
                _step("advanced", "skipped", required=False),
            ]
        )
        self.assertEqual(summary.status, Scan.Status.COMPLETED)

    def test_optional_unavailable_step_does_not_downgrade_success(self) -> None:
        """An optional tool missing from the image is not lost coverage."""
        summary = aggregate_scan_status(
            [
                _step("website", "completed"),
                _step("lighthouse", "unavailable", required=False),
            ]
        )
        self.assertEqual(summary.status, Scan.Status.COMPLETED)
        self.assertEqual(summary.incomplete, ())

    def test_required_budget_skip_is_incomplete(self) -> None:
        summary = aggregate_scan_status(
            [
                _step("website", "completed"),
                _step("nuclei", "skipped", required=True),
            ]
        )
        self.assertEqual(summary.status, Scan.Status.PARTIAL)
        self.assertIn("nuclei skipped", summary.reason)

    def test_no_steps_is_failed(self) -> None:
        self.assertEqual(aggregate_scan_status([]).status, Scan.Status.FAILED)
        self.assertEqual(aggregate_scan_status(None).status, Scan.Status.FAILED)


class OrchestratorStatusTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            "status-integrity@example.com", "CorrectHorseBattery1!"
        )
        self.website = Website.objects.create(
            owner=self.user, domain="status-integrity.example"
        )

    def _scanner(
        self,
        name: str,
        *,
        timed_out: bool = False,
        failed: bool = False,
        score: int | None = 20,
    ) -> MagicMock:
        scanner = MagicMock()
        scanner.name = name
        scanner.scanner_type = ScannerType.INTERNAL
        scanner.timeout = 60
        scanner.is_available.return_value = True
        if failed:
            scanner.execute.side_effect = RuntimeError("scanner process crashed")
            return scanner
        details = {}
        if timed_out:
            details = {
                "scan_complete": False,
                "timed_out": True,
                "partial_reason": "timeout",
                "exit_code": -9,
            }
        scanner.execute.return_value = ScanOutcome(
            result=ScanResult(
                score=score,
                status="warning" if timed_out else "healthy",
                message="timeout" if timed_out else "ok",
                details=details,
            ),
            findings=[],
        )
        return scanner

    def _run(self, scanners: dict[str, MagicMock], steps: list[dict]):
        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.QUEUED,
            scan_type=Scan.ScanType.FULL,
        )
        with (
            patch("scanners.registry.ScannerRegistry", autospec=True) as registry,
            patch(
                "scans.services.steps_builder.build_initial_steps",
                return_value=steps,
            ),
            patch("scans.services.scoring.recalculate_scan_health"),
            patch(
                "advisory.services.scan_ingestion.ingest_scan_findings",
                return_value=None,
            ) as ingest,
            override_settings(
                SCANNER_ARCHIVE_ENABLED=False,
            ),
        ):
            registry.get.side_effect = lambda name: scanners[name]
            ScanOrchestrator(scan.id).run()
        scan.refresh_from_db()
        return scan, ingest

    def test_3584_case_zap_success_and_nuclei_timeout_is_partial(self) -> None:
        """Reproduce the real 3584 shape: one usable scanner + Nuclei timeout."""
        scan, ingest = self._run(
            {
                "zap": self._scanner("zap"),
                "nuclei": self._scanner("nuclei", timed_out=True, score=None),
            },
            [_step("zap", "pending"), _step("nuclei", "pending")],
        )

        self.assertEqual(scan.status, Scan.Status.PARTIAL)
        self.assertIn("nuclei timeout", scan.failure_message)
        self.assertIsNotNone(scan.completed_at)

        runs = {run.scanner: run for run in ScannerRun.objects.filter(scan=scan)}
        self.assertEqual(runs["zap"].status, ScannerRun.Status.COMPLETED)
        self.assertEqual(runs["nuclei"].status, ScannerRun.Status.TIMEOUT)
        steps = {step["key"]: step for step in scan.steps}
        self.assertEqual(steps["nuclei"]["status"], "timeout")
        self.assertEqual(steps["zap"]["status"], "completed")

        calls = {
            call.kwargs["scanner_name"]: call.kwargs for call in ingest.call_args_list
        }
        self.assertTrue(calls["zap"]["complete"])
        self.assertFalse(calls["nuclei"]["complete"])

    def test_all_scanners_failed_marks_scan_failed(self) -> None:
        scan, _ = self._run(
            {
                "zap": self._scanner("zap", failed=True),
                "nuclei": self._scanner("nuclei", failed=True),
            },
            [_step("zap", "pending"), _step("nuclei", "pending")],
        )
        self.assertEqual(scan.status, Scan.Status.FAILED)
        self.assertIn("no usable scanner result", scan.failure_message)

    def test_partial_scan_is_terminal_and_idempotent(self) -> None:
        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.PARTIAL,
            failure_message="Partial scan: nuclei timeout.",
            completed_at=timezone.now(),
        )
        with patch("scans.services.steps_builder.build_initial_steps") as build_steps:
            ScanOrchestrator(scan.id).run()
        build_steps.assert_not_called()
        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.PARTIAL)
        self.assertEqual(ScannerRun.objects.filter(scan=scan).count(), 0)

    def test_celery_retry_cannot_downgrade_partial_to_completed(self) -> None:
        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.QUEUED,
            scan_type=Scan.ScanType.FULL,
        )

        def crash_after_partial(orchestrator_self):
            Scan.objects.filter(pk=orchestrator_self.scan_id).update(
                status=Scan.Status.PARTIAL,
                failure_message="Partial scan: nuclei timeout.",
                completed_at=timezone.now(),
            )
            raise RuntimeError("late failure after partial result")

        with patch.object(ScanOrchestrator, "run", crash_after_partial):
            with self.assertRaises(RuntimeError):
                run_authenticated_scan.apply(args=[scan.pk]).get()

        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.PARTIAL)
        self.assertIn("nuclei timeout", scan.failure_message)


class ScanStatusApiTests(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            "status-api@example.com", "CorrectHorseBattery1!"
        )
        self.other = User.objects.create_user(
            "status-api-other@example.com", "CorrectHorseBattery1!"
        )
        self.website = Website.objects.create(
            owner=self.user, domain="status-api.example"
        )
        self.scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.PARTIAL,
            health_score=62,
            failure_message="Partial scan: nuclei timeout.",
            completed_at=timezone.now(),
        )
        ScannerRun.objects.create(
            scan=self.scan,
            scanner="zap",
            status=ScannerRun.Status.COMPLETED,
        )
        ScannerRun.objects.create(
            scan=self.scan,
            scanner="nuclei",
            status=ScannerRun.Status.TIMEOUT,
            error_message="process exceeded its 150s budget",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}"
        )

    def test_list_filter_returns_partial_scan(self) -> None:
        response = self.client.get("/api/v1/scans/?status=partial")
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.scan.id])
        self.assertEqual(response.data["results"][0]["status"], "partial")

    def test_detail_exposes_partial_status_and_reason(self) -> None:
        response = self.client.get(f"/api/v1/scans/{self.scan.id}/")
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "partial")
        self.assertIn("nuclei timeout", response.data["failure_message"])

    def test_scanner_runs_endpoint_exposes_timeout(self) -> None:
        response = self.client.get(f"/api/v1/scans/{self.scan.id}/scanner-runs/")
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        statuses = {row["scanner"]: row["status"] for row in response.data}
        self.assertEqual(statuses["zap"], "completed")
        self.assertEqual(statuses["nuclei"], "timeout")

    def test_other_tenant_cannot_read_partial_scan(self) -> None:
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.other)}"
        )
        response = self.client.get(f"/api/v1/scans/{self.scan.id}/")
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
