"""Orchestrator gate for the opt-in advanced security tier."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings

from accounts.models import User
from scanners.base import BaseScanner, ScanResult, ScannerType
from scans.models import Scan, ScannerRun
from scans.services.orchestrator import ScanOrchestrator
from websites.models import Website


class AdvancedScanner(BaseScanner):
    name = "advanced"
    scanner_type = ScannerType.INTERNAL
    requires_advanced_security = True

    def __init__(self) -> None:
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def scan(self, domain: str) -> ScanResult:
        self.calls += 1
        return ScanResult(
            score=None,
            status="neutral",
            message="advanced scan ran",
            details={},
        )


def _step() -> dict:
    return {
        "key": "advanced",
        "label": "Advanced scan",
        "scanner": "advanced",
        "weight": 100,
        "status": "pending",
        "progress": 0,
        "duration_ms": None,
        "error": None,
    }


class AdvancedSecurityGateTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            "advanced-gate@example.com", "CorrectHorseBattery1!"
        )
        self.website = Website.objects.create(owner=user, domain="example.com")

    def _run(self, scanner: AdvancedScanner) -> Scan:
        scan = Scan.objects.create(
            website=self.website, status=Scan.Status.QUEUED
        )
        with patch(
            "scanners.registry.ScannerRegistry.get", return_value=scanner
        ), patch(
            "scans.services.steps_builder.build_initial_steps",
            return_value=[_step()],
        ), patch(
            "scans.services.scoring.recalculate_scan_health"
        ):
            ScanOrchestrator(scan.id).run()
        scan.refresh_from_db()
        return scan

    @override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=False)
    def test_advanced_step_is_skipped_when_flag_is_off(self):
        scanner = AdvancedScanner()
        scan = self._run(scanner)

        self.assertEqual(scanner.calls, 0)
        self.assertEqual(scan.steps[0]["status"], "skipped")
        self.assertIn(
            "SCANNER_ADVANCED_SECURITY_ENABLED=false",
            scan.steps[0]["error"],
        )
        self.assertEqual(ScannerRun.objects.filter(scan=scan).count(), 0)
        # The policy skip is optional, but no scanner produced a result either.
        self.assertEqual(scan.status, Scan.Status.FAILED)
        self.assertIn("no usable scanner result", scan.failure_message)

    @override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=True)
    def test_advanced_step_runs_when_flag_is_on(self):
        scanner = AdvancedScanner()
        scan = self._run(scanner)

        self.assertEqual(scanner.calls, 1)
        self.assertEqual(scan.steps[0]["status"], "completed")
        self.assertEqual(ScannerRun.objects.filter(scan=scan).count(), 1)
