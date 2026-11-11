"""Regression: a Nuclei sandbox failure must never complete a journey.

The adapter used to return a result without ``scan_complete`` when the sandbox
could not start the tool.  The orchestrator's legacy fallback then treated the
step as completed, so a stage-2 journey whose Nuclei never ran was reported as
``completed`` (observed on the 2026-11-04 E2E run, scan 882).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase

from accounts.models import User
from scans.models import JourneyState, Scan, ScanJourney, ScannerRun
from scans.services.journey_service import JourneyService
from scans.services.orchestrator import ScanOrchestrator
from scanners.base import ScannerType
from scanners.executors.sandbox import SandboxError, SandboxLimits, SandboxMode
from scanners.implementations.nuclei import NucleiScanner
from scanners.security.target_validator import TargetInfo
from websites.models import Website


def _step(key: str, scanner: str, weight: int = 100) -> dict:
    return {
        "key": key,
        "label": key.title(),
        "scanner": scanner,
        "weight": weight,
        "status": "pending",
        "progress": 0,
        "duration_ms": None,
        "error": None,
    }


def _target() -> TargetInfo:
    return TargetInfo(
        hostname="example.com",
        url="https://example.com",
        safe_ips=["93.184.216.34"],
        scheme="https",
    )


class SandboxUnavailableJourneyTests(TestCase):
    def test_sandbox_error_makes_stage_two_partial(self) -> None:
        user = User.objects.create_user(
            "sandbox-regression@example.com", "CorrectHorseBattery1!"
        )
        website = Website.objects.create(owner=user, domain="example.com")
        journey = ScanJourney.objects.create(
            website=website,
            requested_by=user,
            state=JourneyState.RUNNING,
            current_stage=2,
            total_stages=2,
        )
        scan = Scan.objects.create(
            website=website,
            scan_type=Scan.ScanType.SECURITY,
            status=Scan.Status.QUEUED,
            journey=journey,
            journey_stage=2,
            quota_charged=False,
        )

        executor = MagicMock()
        executor.mode = SandboxMode.DOCKER
        executor.run.side_effect = SandboxError("Bind mount source is not a directory")
        executor.limits_for.return_value = SandboxLimits(timeout_s=60, cpu_seconds=65)

        with (
            patch("scanners.registry.ScannerRegistry") as registry,
            patch(
                "scans.services.steps_builder.build_initial_steps",
                return_value=[_step("nuclei", "nuclei")],
            ),
            patch(
                "scanners.security.target_validator.validate_target",
                return_value=_target(),
            ),
            patch(
                "scanners.executors.sandbox.get_sandbox_executor",
                return_value=executor,
            ),
            patch(
                "scanners.implementations.nuclei.get_sandbox_executor",
                return_value=executor,
            ),
            patch(
                "scanners.features.advanced_security_enabled",
                return_value=True,
            ),
            patch(
                "scanners.implementations.nuclei.advanced_security_enabled",
                return_value=True,
            ),
            patch.object(NucleiScanner, "is_available", return_value=True),
        ):
            registry.get.return_value = NucleiScanner()
            ScanOrchestrator(scan.pk).run()

        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.PARTIAL)
        step = next(item for item in scan.steps if item["key"] == "nuclei")
        self.assertEqual(step["status"], "partial")
        self.assertEqual(step["error"], "sandbox_unavailable")

        run = ScannerRun.objects.get(scan=scan)
        self.assertEqual(run.status, ScannerRun.Status.PARTIAL)
        self.assertFalse(run.metadata["scan_complete"])
        self.assertEqual(run.metadata["partial_reason"], "sandbox_unavailable")

        journey = JourneyService.on_stage_completed(scan.pk)
        self.assertEqual(journey.state, JourneyState.PARTIAL)
        self.assertNotEqual(journey.state, JourneyState.COMPLETED)
