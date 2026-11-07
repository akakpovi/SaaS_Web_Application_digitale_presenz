"""ScanOrchestrator delegation tests.

Covers the policy layer added for external tools:

* central SSRF validation before any target is handed to a delegated tool;
* per-step timeout clamping and overall scan budget;
* the ``ScanContext`` handed to adapters (validated target + deadline);
* CheckResult merging when two tools measure the same category.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from accounts.models import User
from scanners.base import (
    BaseScanner,
    ScanContext,
    ScanOutcome,
    ScanResult,
    ScannerType,
)
from scanners.base import NormalizedFinding, Severity, FindingStatus
from scanners.implementations.nuclei import NucleiScanner
from scanners.security.target_validator import TargetInfo
from scans.models import CheckResult, Finding, Scan, ScannerRun
from scans.services.orchestrator import ScanOrchestrator
from websites.models import Website


def _user() -> User:
    return User.objects.create_user("delegation@example.com", "CorrectHorseBattery1!")


def _website(user: User, domain: str = "example.com") -> Website:
    return Website.objects.create(owner=user, domain=domain)


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


class RecordingScanner(BaseScanner):
    """External scanner that records the context it receives."""

    name = "recording"
    scanner_type = ScannerType.CLI
    timeout = 60

    def __init__(self) -> None:
        self.captured: ScanContext | None = None

    def is_available(self) -> bool:
        return True

    def scan(self, domain: str) -> ScanResult:
        return ScanResult(score=None, status="neutral", message="", details={})

    def execute(self, domain: str, context: ScanContext | None = None) -> ScanOutcome:
        self.captured = context
        return ScanOutcome(
            result=ScanResult(
                score=None,
                status="neutral",
                message="delegated",
                details={},
            ),
            findings=[],
        )


class CentralSSRFGateTests(TestCase):
    def setUp(self):
        self.user = _user()

    @patch("scanners.registry.ScannerRegistry")
    def test_external_scanner_with_internal_target_is_never_invoked(
        self, mock_registry
    ):
        # ``metadata.google.internal`` is rejected by core.security without
        # any DNS lookup: the suffix alone marks it internal.
        website = _website(self.user, "metadata.google.internal")

        scanner = MagicMock()
        scanner.name = "testssl"
        scanner.scanner_type = ScannerType.CLI
        scanner.timeout = 60
        scanner.is_available.return_value = True
        mock_registry.get.return_value = scanner

        scan = Scan.objects.create(website=website, status=Scan.Status.QUEUED)

        with patch(
            "scans.services.steps_builder.build_initial_steps",
            return_value=[_step("testssl", "testssl")],
        ), patch("scans.services.scoring.recalculate_scan_health"):
            ScanOrchestrator(scan.id).run()

        scanner.scan.assert_not_called()
        scanner.execute.assert_not_called()

        scan.refresh_from_db()
        # The only required scanner was blocked and produced no usable result.
        self.assertEqual(scan.status, Scan.Status.FAILED)
        self.assertIn("no usable scanner result", scan.failure_message)

        run = ScannerRun.objects.get(scan=scan)
        self.assertEqual(run.status, "failed")
        self.assertTrue(run.metadata["blocked"])
        self.assertEqual(run.metadata["reason"], "ssrf")
        self.assertFalse(run.metadata["target_validated"])

        step = next(s for s in scan.steps if s["key"] == "testssl")
        self.assertEqual(step["status"], "failed")
        self.assertIn("SSRF", step["error"])

    @patch("scanners.registry.ScannerRegistry")
    def test_raw_ip_target_is_blocked(self, mock_registry):
        website = _website(self.user, "169.254.169.254")

        scanner = MagicMock()
        scanner.name = "nmap"
        scanner.scanner_type = ScannerType.CLI
        scanner.timeout = 60
        scanner.is_available.return_value = True
        mock_registry.get.return_value = scanner

        scan = Scan.objects.create(website=website, status=Scan.Status.QUEUED)

        with patch(
            "scans.services.steps_builder.build_initial_steps",
            return_value=[_step("nmap", "nmap")],
        ), patch("scans.services.scoring.recalculate_scan_health"):
            ScanOrchestrator(scan.id).run()

        scanner.scan.assert_not_called()
        self.assertEqual(
            ScannerRun.objects.get(scan=scan).metadata["reason"], "ssrf"
        )

    @patch("scanners.registry.ScannerRegistry")
    def test_internal_scanners_do_not_require_the_gate(self, mock_registry):
        scanner = MagicMock()
        scanner.name = "website"
        scanner.scanner_type = ScannerType.INTERNAL
        scanner.timeout = 15
        scanner.is_available.return_value = True
        scanner.scan.return_value = ScanResult(
            score=20, status="healthy", message="ok", details={}
        )
        scanner.scan_findings.return_value = []
        mock_registry.get.return_value = scanner

        scan = Scan.objects.create(
            website=_website(self.user), status=Scan.Status.QUEUED
        )

        with patch(
            "scans.services.steps_builder.build_initial_steps",
            return_value=[_step("website", "website")],
        ), patch(
            "scanners.security.target_validator.validate_target"
        ) as mock_validate, patch(
            "scans.services.scoring.recalculate_scan_health"
        ):
            ScanOrchestrator(scan.id).run()

        mock_validate.assert_not_called()
        self.assertEqual(
            ScannerRun.objects.get(scan=scan).status, "completed"
        )

    @patch("scanners.registry.ScannerRegistry")
    def test_unavailable_tool_is_reported_before_any_dns_lookup(
        self, mock_registry
    ):
        scanner = MagicMock()
        scanner.name = "lighthouse"
        scanner.scanner_type = ScannerType.CLI
        scanner.timeout = 120
        scanner.is_available.return_value = False
        mock_registry.get.return_value = scanner

        scan = Scan.objects.create(
            website=_website(self.user), status=Scan.Status.QUEUED
        )

        with patch(
            "scans.services.steps_builder.build_initial_steps",
            return_value=[_step("lighthouse", "lighthouse")],
        ), patch(
            "scanners.security.target_validator.validate_target"
        ) as mock_validate, patch(
            "scans.services.scoring.recalculate_scan_health"
        ):
            ScanOrchestrator(scan.id).run()

        mock_validate.assert_not_called()
        run = ScannerRun.objects.get(scan=scan)
        self.assertEqual(run.status, "unavailable")
        self.assertIn("binary not found", run.error_message)


class NucleiProfileBudgetTests(TestCase):
    """The sandbox must receive the active profile's budget, not a stale cap."""

    def setUp(self):
        self.user = _user()

    def _nuclei_config(self, profile: str, timeout: int) -> dict:
        return {
            "nuclei": {
                "profile": profile,
                "timeout": 170,  # legacy top-level value
                "profiles": {
                    profile: {
                        "timeout": timeout,
                        "severity": "critical,high",
                        "tags": ["exposure", "misconfig"],
                    }
                },
                "sandbox": {"memory_mb": 1536},
            }
        }

    def test_standard_profile_wins_over_legacy_top_level(self):
        scan = Scan.objects.create(
            website=_website(self.user), status=Scan.Status.QUEUED
        )
        orchestrator = ScanOrchestrator(scan.id)
        orchestrator._deadline = time.monotonic() + 540.9

        scanner = NucleiScanner()
        with override_settings(
            SCANNER_CONFIG=self._nuclei_config("standard", 150),
            SCANNER_SANDBOX={"max_timeout": 300},
        ):
            self.assertEqual(
                orchestrator._effective_timeout(scanner, "nuclei"), 150
            )

    def test_thorough_profile_keeps_its_own_budget(self):
        scan = Scan.objects.create(
            website=_website(self.user), status=Scan.Status.QUEUED
        )
        orchestrator = ScanOrchestrator(scan.id)
        orchestrator._deadline = time.monotonic() + 540.9

        scanner = NucleiScanner()
        with override_settings(
            SCANNER_CONFIG=self._nuclei_config("thorough", 178),
            SCANNER_SANDBOX={"max_timeout": 300},
        ):
            self.assertEqual(
                orchestrator._effective_timeout(scanner, "nuclei"), 178
            )

    def test_profile_budget_is_clamped_by_sandbox_max(self):
        scan = Scan.objects.create(
            website=_website(self.user), status=Scan.Status.QUEUED
        )
        orchestrator = ScanOrchestrator(scan.id)
        orchestrator._deadline = time.monotonic() + 540.9

        scanner = NucleiScanner()
        with override_settings(
            SCANNER_CONFIG=self._nuclei_config("thorough", 178),
            SCANNER_SANDBOX={"max_timeout": 120},
        ):
            self.assertEqual(
                orchestrator._effective_timeout(scanner, "nuclei"), 120
            )


class PartialRunStatusTests(TestCase):
    """A partial/timeout run must not be presented as a completed step."""

    def setUp(self):
        self.user = _user()

    def _scanner(self, *, timed_out: bool, reason: str) -> MagicMock:
        scanner = MagicMock()
        scanner.name = "nuclei"
        scanner.scanner_type = ScannerType.CLI
        scanner.timeout = 150
        scanner.profile_timeout = 150
        scanner.is_available.return_value = True
        scanner.execute.return_value = ScanOutcome(
            result=ScanResult(
                score=None,
                status="warning",
                message="Nuclei incomplete",
                details={
                    "scan_complete": False,
                    "timed_out": timed_out,
                    "partial_reason": reason,
                    "duration_alert_s": 150,
                    "duration_over_alert": False,
                },
            ),
            findings=[],
        )
        return scanner

    def _run_with(self, scanner: MagicMock) -> Scan:
        with patch("scanners.registry.ScannerRegistry") as mock_registry, \
             patch(
                 "scans.services.steps_builder.build_initial_steps",
                 return_value=[_step("nuclei", "nuclei")],
             ), \
             patch(
                 "scanners.security.target_validator.validate_target",
                 return_value=_target(),
             ), \
             patch("scans.services.scoring.recalculate_scan_health"):
            mock_registry.get.return_value = scanner
            scan = Scan.objects.create(
                website=_website(self.user), status=Scan.Status.QUEUED
            )
            ScanOrchestrator(scan.id).run()
        scan.refresh_from_db()
        return scan

    def test_timeout_run_has_timeout_status_and_no_resolution(self):
        scan = self._run_with(self._scanner(timed_out=True, reason="timeout"))

        run = ScannerRun.objects.get(scan=scan)
        self.assertEqual(run.status, ScannerRun.Status.TIMEOUT)
        self.assertFalse(run.metadata["scan_complete"])
        step = next(s for s in scan.steps if s["key"] == "nuclei")
        self.assertEqual(step["status"], "timeout")
        self.assertEqual(step["error"], "timeout")

    def test_partial_run_has_partial_status(self):
        scan = self._run_with(
            self._scanner(timed_out=False, reason="host_unresponsive")
        )

        run = ScannerRun.objects.get(scan=scan)
        self.assertEqual(run.status, ScannerRun.Status.PARTIAL)
        step = next(s for s in scan.steps if s["key"] == "nuclei")
        self.assertEqual(step["status"], "partial")
        self.assertEqual(step["error"], "host_unresponsive")


class ArchiveHookTests(TestCase):
    """Nuclei reports are archived without making the scan depend on storage."""

    def setUp(self):
        self.user = _user()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.archive_root = Path(self.tmp.name) / "archives"

    def _scanner(self, *, raw_report: str = '{"template-id":"x"}'):
        scanner = MagicMock()
        scanner.name = "nuclei"
        scanner.scanner_type = ScannerType.CLI
        scanner.timeout = 150
        scanner.profile_timeout = 150
        scanner.is_available.return_value = True
        scanner.execute.return_value = ScanOutcome(
            result=ScanResult(
                score=None,
                status="neutral",
                message="Nuclei complete",
                details={
                    "scan_complete": True,
                    "resolve_missing": False,
                    "partial_reason": "",
                    "exit_code": 0,
                    "profile": "standard",
                },
            ),
            findings=[
                NormalizedFinding(
                    check_code="nuclei.exposed-env-file",
                    category="security",
                    severity=Severity.HIGH,
                    status=FindingStatus.FAIL,
                    title="Exposed .env File",
                )
            ],
            raw_report=raw_report,
            raw_report_format="nuclei-jsonl",
            raw_report_meta={"profile": "standard", "scan_complete": True},
        )
        return scanner

    def _run(self, scanner: MagicMock):
        with patch("scanners.registry.ScannerRegistry") as mock_registry, \
             patch(
                 "scans.services.steps_builder.build_initial_steps",
                 return_value=[_step("nuclei", "nuclei")],
             ), \
             patch(
                 "scanners.security.target_validator.validate_target",
                 return_value=_target(),
             ), \
             patch("scans.services.scoring.recalculate_scan_health"), \
             override_settings(
                 SCANNER_ARCHIVE_ENABLED=True,
                 SCANNER_ARCHIVE_DIR=str(self.archive_root),
                 SCANNER_ARCHIVE_MAX_BYTES=1024 * 1024,
                 SCANNER_ARCHIVE_RETENTION_DAYS=30,
             ):
            mock_registry.get.return_value = scanner
            scan = Scan.objects.create(
                website=_website(self.user), status=Scan.Status.QUEUED
            )
            ScanOrchestrator(scan.id).run()
        return scan

    def test_complete_report_is_archived_and_linked_to_scanner_run(self):
        scan = self._run(self._scanner())
        run = ScannerRun.objects.get(scan=scan)

        self.assertEqual(run.status, ScannerRun.Status.COMPLETED)
        self.assertEqual(run.metadata["archive"]["status"], "stored")
        self.assertEqual(run.metadata["archive"]["records"], 1)
        self.assertTrue((self.archive_root / run.metadata["archive"]["ref"]).is_file())

    def test_archive_failure_is_recorded_but_does_not_block_ingestion(self):
        scanner = self._scanner()
        with patch(
            "scanners.artifacts.archive_report",
            side_effect=RuntimeError("storage offline"),
        ), patch(
            "advisory.services.scan_ingestion.ingest_scan_findings",
            return_value=None,
        ) as ingest:
            scan = self._run(scanner)

        scan.refresh_from_db()
        run = ScannerRun.objects.get(scan=scan)
        self.assertEqual(scan.status, Scan.Status.COMPLETED)
        self.assertEqual(run.metadata["archive"]["status"], "failed")
        self.assertEqual(run.metadata["archive"]["detail"], "RuntimeError")
        ingest.assert_called_once()

    def test_timeout_partial_report_is_archived_but_not_complete(self):
        scanner = self._scanner(raw_report='{"template-id":"partial"}')
        scanner.execute.return_value.result.details.update(
            {"scan_complete": False, "timed_out": True, "partial_reason": "timeout"}
        )
        scan = self._run(scanner)
        run = ScannerRun.objects.get(scan=scan)

        self.assertEqual(run.status, ScannerRun.Status.TIMEOUT)
        self.assertEqual(run.metadata["archive"]["status"], "stored")
        self.assertTrue(run.metadata["archive"]["partial"])

    def test_timeout_without_output_records_an_explicit_limitation(self):
        scanner = self._scanner(raw_report="")
        scanner.execute.return_value.result.details.update(
            {"scan_complete": False, "timed_out": True, "partial_reason": "timeout"}
        )
        scan = self._run(scanner)
        run = ScannerRun.objects.get(scan=scan)

        self.assertEqual(run.metadata["archive"]["status"], "unavailable")
        self.assertEqual(run.metadata["archive"]["detail"], "empty_report")
        self.assertTrue(run.metadata["archive"]["partial"])
        self.assertEqual(len(list(self.archive_root.rglob("*.jsonl"))), 0)


class DelegationContextTests(TestCase):
    def setUp(self):
        self.user = _user()

    @patch("scanners.registry.ScannerRegistry")
    def test_context_carries_validated_target_and_timeout(self, mock_registry):
        scanner = RecordingScanner()
        mock_registry.get.return_value = scanner

        scan = Scan.objects.create(
            website=_website(self.user), status=Scan.Status.QUEUED
        )

        with patch(
            "scans.services.steps_builder.build_initial_steps",
            return_value=[_step("recording", "recording")],
        ), patch(
            "scanners.security.target_validator.validate_target",
            return_value=_target(),
        ) as mock_validate, patch(
            "scans.services.scoring.recalculate_scan_health"
        ):
            ScanOrchestrator(scan.id).run()

        mock_validate.assert_called_once_with("https://example.com")
        self.assertIsNotNone(scanner.captured)
        self.assertEqual(scanner.captured.domain, "example.com")
        self.assertEqual(scanner.captured.target.hostname, "example.com")
        self.assertEqual(scanner.captured.timeout, 60)
        # The orchestrator computes the resource envelope for the adapter.
        self.assertIsNotNone(scanner.captured.sandbox_limits)
        self.assertEqual(scanner.captured.sandbox_limits.memory_mb, 512)

        run = ScannerRun.objects.get(scan=scan)
        self.assertTrue(run.metadata["target_validated"])
        self.assertEqual(run.metadata["timeout_s"], 60)
        self.assertEqual(run.metadata["scanner_type"], ScannerType.CLI)
        self.assertEqual(run.metadata["memory_mb"], 512)
        self.assertEqual(run.metadata["cpu_seconds"], 65)

    def test_effective_timeout_is_clamped_by_remaining_budget(self):
        scan = Scan.objects.create(
            website=_website(self.user), status=Scan.Status.QUEUED
        )
        orchestrator = ScanOrchestrator(scan.id)
        # +10.9 keeps ``int(remaining)`` at 10 despite the elapsed test time.
        orchestrator._deadline = time.monotonic() + 10.9

        scanner = MagicMock()
        scanner.timeout = 120

        with override_settings(
            SCANNER_CONFIG={"lighthouse": {"timeout": 120}},
            SCANNER_SANDBOX={"max_timeout": 300},
        ):
            self.assertEqual(
                orchestrator._effective_timeout(scanner, "lighthouse"), 10
            )

    def test_effective_timeout_is_clamped_by_sandbox_max(self):
        scan = Scan.objects.create(
            website=_website(self.user), status=Scan.Status.QUEUED
        )
        orchestrator = ScanOrchestrator(scan.id)
        orchestrator._deadline = time.monotonic() + 600

        scanner = MagicMock()
        scanner.timeout = 120

        with override_settings(
            SCANNER_CONFIG={"lighthouse": {"timeout": 120}},
            SCANNER_SANDBOX={"max_timeout": 45},
        ):
            self.assertEqual(
                orchestrator._effective_timeout(scanner, "lighthouse"), 45
            )

    def test_exhausted_budget_skips_all_remaining_steps(self):
        scan = Scan.objects.create(
            website=_website(self.user), status=Scan.Status.QUEUED
        )
        orchestrator = ScanOrchestrator(scan.id)
        orchestrator._deadline = time.monotonic() - 1

        steps = [
            _step("website", "website", 50),
            _step("ssl", "ssl", 50),
        ]

        with patch("scanners.registry.ScannerRegistry") as mock_registry:
            orchestrator._run_all_steps(scan, "example.com", steps)
            mock_registry.get.assert_not_called()

        self.assertEqual(ScannerRun.objects.filter(scan=scan).count(), 0)
        self.assertTrue(all(step["status"] == "skipped" for step in steps))
        self.assertTrue(all("budget" in step["error"] for step in steps))


class CheckResultDelegationTests(TestCase):
    def setUp(self):
        self.user = _user()

    @patch("scanners.registry.ScannerRegistry")
    def test_lighthouse_supersedes_legacy_performance_result(self, mock_registry):
        legacy = MagicMock()
        legacy.name = "performance"
        legacy.scanner_type = ScannerType.INTERNAL
        legacy.check_result_category = None
        legacy.timeout = 15
        legacy.is_available.return_value = True
        legacy.execute.return_value = ScanOutcome(
            result=ScanResult(
                score=11,
                status="warning",
                message="legacy performance",
                details={"load_time_ms": 1400},
            ),
            findings=[],
        )

        lighthouse = MagicMock()
        lighthouse.name = "lighthouse"
        lighthouse.scanner_type = ScannerType.INTERNAL
        lighthouse.check_result_category = "performance"
        lighthouse.timeout = 120
        lighthouse.is_available.return_value = True
        lighthouse.execute.return_value = ScanOutcome(
            result=ScanResult(
                score=13,
                status="healthy",
                message="Lighthouse performance 87/100, SEO 100/100",
                details={"category_scores": {"performance": 87, "seo": 100}},
            ),
            findings=[
                NormalizedFinding(
                    check_code="lighthouse.seo_score",
                    category="seo",
                    severity=Severity.INFO,
                    status=FindingStatus.PASS,
                    title="Lighthouse SEO score: 100/100",
                )
            ],
        )

        mock_registry.get.side_effect = lambda name: {
            "performance": legacy,
            "lighthouse": lighthouse,
        }[name]

        scan = Scan.objects.create(
            website=_website(self.user), status=Scan.Status.QUEUED
        )

        with patch(
            "scans.services.steps_builder.build_initial_steps",
            return_value=[
                _step("performance", "performance", 50),
                _step("lighthouse", "lighthouse", 50),
            ],
        ), patch("scans.services.scoring.recalculate_scan_health"):
            ScanOrchestrator(scan.id).run()

        result = CheckResult.objects.get(scan=scan, category="performance")
        self.assertEqual(result.score, 13)
        self.assertEqual(result.summary, "Lighthouse performance 87/100, SEO 100/100")
        self.assertEqual(result.technical_details["scanner"], "lighthouse")
        self.assertEqual(
            result.technical_details["previous_measurement"]["score"], 11
        )

        finding = Finding.objects.get(
            scanner_run__scan=scan, check_code="lighthouse.seo_score"
        )
        self.assertEqual(finding.category, "seo")
        self.assertEqual(finding.status, "pass")

    @patch("scanners.registry.ScannerRegistry")
    def test_legacy_performance_is_kept_when_lighthouse_fails(self, mock_registry):
        legacy = MagicMock()
        legacy.name = "performance"
        legacy.scanner_type = ScannerType.INTERNAL
        legacy.check_result_category = None
        legacy.timeout = 15
        legacy.is_available.return_value = True
        legacy.execute.return_value = ScanOutcome(
            result=ScanResult(
                score=12,
                status="healthy",
                message="legacy performance",
                details={},
            ),
            findings=[],
        )

        lighthouse = MagicMock()
        lighthouse.name = "lighthouse"
        lighthouse.scanner_type = ScannerType.CLI
        lighthouse.check_result_category = "performance"
        lighthouse.timeout = 120
        lighthouse.is_available.return_value = True
        lighthouse.execute.side_effect = RuntimeError("Chromium crashed")

        mock_registry.get.side_effect = lambda name: {
            "performance": legacy,
            "lighthouse": lighthouse,
        }[name]

        scan = Scan.objects.create(
            website=_website(self.user), status=Scan.Status.QUEUED
        )

        with patch(
            "scans.services.steps_builder.build_initial_steps",
            return_value=[
                _step("performance", "performance", 50),
                _step("lighthouse", "lighthouse", 50),
            ],
        ), patch(
            "scanners.security.target_validator.validate_target",
            return_value=_target(),
        ), patch("scans.services.scoring.recalculate_scan_health"):
            ScanOrchestrator(scan.id).run()

        result = CheckResult.objects.get(scan=scan, category="performance")
        self.assertEqual(result.score, 12)
        self.assertEqual(result.summary, "legacy performance")

        runs = {run.scanner: run for run in ScannerRun.objects.filter(scan=scan)}
        self.assertEqual(runs["lighthouse"].status, "failed")


def _external_scanner(
    name: str,
    *,
    score: int | None,
    status: str,
    details: dict,
    findings: list[NormalizedFinding],
) -> MagicMock:
    """Mock external adapter that returns one ScanOutcome."""
    scanner = MagicMock()
    scanner.name = name
    scanner.scanner_type = ScannerType.CLI
    scanner.check_result_category = None
    scanner.timeout = 120
    scanner.is_available.return_value = True
    scanner.execute.return_value = ScanOutcome(
        result=ScanResult(
            score=score,
            status=status,
            message=f"{name} summary",
            details=details,
        ),
        findings=findings,
    )
    return scanner


class ExternalCheckResultMappingTests(TestCase):
    """testssl and Gobuster feed the CheckResult bridge explicitly."""

    def setUp(self):
        self.user = _user()
        self.website = _website(self.user)

    def _run(self, scanner: MagicMock, key: str) -> Scan:
        scan = Scan.objects.create(
            website=self.website, status=Scan.Status.QUEUED
        )
        with patch("scanners.registry.ScannerRegistry") as mock_registry, patch(
            "scans.services.steps_builder.build_initial_steps",
            return_value=[_step(key, key)],
        ), patch(
            "scanners.security.target_validator.validate_target",
            return_value=_target(),
        ), patch(
            "scans.services.scoring.recalculate_scan_health"
        ):
            mock_registry.get.return_value = scanner
            ScanOrchestrator(scan.id).run()
        return scan

    def test_testssl_findings_create_an_ssl_check_result(self):
        scanner = _external_scanner(
            "testssl",
            score=15,
            status="critical",
            details={"scan_complete": True, "total_checks": 2},
            findings=[
                NormalizedFinding(
                    check_code="testssl.TLS1_0",
                    category="ssl",
                    severity=Severity.HIGH,
                    status=FindingStatus.FAIL,
                    title="TLS 1.0 offered",
                )
            ],
        )

        scan = self._run(scanner, "testssl")

        result = CheckResult.objects.get(
            scan=scan, category=CheckResult.Category.SSL
        )
        self.assertEqual(result.score, 15)
        self.assertEqual(result.summary, "testssl summary")
        self.assertEqual(result.technical_details["scanner"], "testssl")

    def test_gobuster_paths_create_an_exposure_check_result(self):
        scanner = _external_scanner(
            "gobuster",
            score=None,
            status="neutral",
            details={
                "scan_complete": True,
                "paths_found": 1,
                "sensitive_paths": 1,
            },
            findings=[
                NormalizedFinding(
                    check_code="gobuster.path.admin",
                    category="security",
                    severity=Severity.HIGH,
                    status=FindingStatus.FAIL,
                    title="Directory/file found: /admin",
                )
            ],
        )

        scan = self._run(scanner, "gobuster")

        result = CheckResult.objects.get(
            scan=scan, category=CheckResult.Category.EXPOSURE
        )
        self.assertIsNone(result.score)
        self.assertEqual(result.technical_details["scanner"], "gobuster")

    def test_empty_external_result_creates_no_check_result(self):
        scanner = _external_scanner(
            "testssl",
            score=20,
            status="neutral",
            details={"scan_complete": True},
            findings=[],
        )

        scan = self._run(scanner, "testssl")

        self.assertFalse(CheckResult.objects.filter(scan=scan).exists())

    def test_incomplete_external_result_creates_no_check_result(self):
        scanner = _external_scanner(
            "gobuster",
            score=None,
            status="warning",
            details={"scan_complete": False},
            findings=[
                NormalizedFinding(
                    check_code="gobuster.path.admin",
                    category="security",
                    severity=Severity.HIGH,
                    status=FindingStatus.FAIL,
                    title="Directory/file found: /admin",
                )
            ],
        )

        scan = self._run(scanner, "gobuster")

        self.assertFalse(CheckResult.objects.filter(scan=scan).exists())
