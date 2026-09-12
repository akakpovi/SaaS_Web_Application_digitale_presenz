"""Scanner Engine tests — Phase 5.

Tests cover:
- ScannerRun / Finding model creation
- New Scan fields (scan_type, progress, current_step, steps)
- Scan type validation: HEALTH / SECURITY / FULL
- Scanner registry
- Orchestrator lifecycle (mocked)
- Progress / current_step / steps updates
- Scanner failure handling (graceful)
- Scanner unavailability handling
- Duplicate active scans → 409
- Ownership permissions
- POST /websites/{id}/scan/ (scan_type support)
- GET /websites/{id}/active_scan/
- Scan filtering (website, status, scan_type)
- /scans/{id}/scanner-runs/ endpoint
- /scans/{id}/findings/ endpoint
- /scans/{id}/recommendations/ endpoint
- Scoring integration
- Recommendation generation
- Steps builder
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from scanners.base import FindingStatus, NormalizedFinding, ScanResult, Severity
from scans.models import CheckResult, Finding, HealthStatus, Scan, ScannerRun
from scans.services.recommendation_engine import Priority, Recommendation, RecommendationEngine
from scans.services.steps_builder import (
    StepStatus,
    build_initial_steps,
    compute_overall_progress,
)
from websites.models import Website


# ─────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────

def make_user(email="owner@example.com"):
    return User.objects.create_user(email, "CorrectHorseBattery1!")


def make_website(owner, domain="example.com"):
    return Website.objects.create(owner=owner, domain=domain)


def make_scan(website, **kwargs):
    kwargs.setdefault("status", Scan.Status.QUEUED)
    return Scan.objects.create(website=website, **kwargs)


def auth_client(client, user):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


# ═══════════════════════════════════════════════════
# ScannerRun model tests
# ═══════════════════════════════════════════════════

class ScannerRunModelTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.website = make_website(self.user)
        self.scan = make_scan(self.website)

    def test_create_scanner_run(self):
        run = ScannerRun.objects.create(scan=self.scan, scanner="nmap")
        self.assertEqual(run.status, ScannerRun.Status.PENDING)
        self.assertIsNone(run.started_at)
        self.assertIsNone(run.finished_at)

    def test_start_sets_running_and_started_at(self):
        run = ScannerRun.objects.create(scan=self.scan, scanner="ssl")
        run.start()
        run.refresh_from_db()
        self.assertEqual(run.status, ScannerRun.Status.RUNNING)
        self.assertIsNotNone(run.started_at)

    def test_finish_completed(self):
        run = ScannerRun.objects.create(scan=self.scan, scanner="dns")
        run.start()
        run.finish(
            status="completed",
            metadata={"findings_count": 3},
            duration_ms=500,
        )
        run.refresh_from_db()
        self.assertEqual(run.status, "completed")
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(run.duration_ms, 500)
        self.assertEqual(run.metadata["findings_count"], 3)

    def test_finish_failed(self):
        run = ScannerRun.objects.create(scan=self.scan, scanner="nmap")
        run.start()
        run.finish(status="failed", error_message="Binary not found", duration_ms=100)
        run.refresh_from_db()
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.error_message, "Binary not found")

    def test_raw_output_truncated_to_50k(self):
        run = ScannerRun.objects.create(scan=self.scan, scanner="nikto")
        run.start()
        big_output = "x" * 100_000
        run.finish(status="completed", raw_output=big_output)
        run.refresh_from_db()
        self.assertLessEqual(len(run.raw_output), 50_001)

    def test_error_message_truncated_to_2000(self):
        run = ScannerRun.objects.create(scan=self.scan, scanner="zap")
        run.start()
        long_error = "e" * 5000
        run.finish(status="failed", error_message=long_error)
        run.refresh_from_db()
        self.assertLessEqual(len(run.error_message), 2001)

    def test_scanner_runs_related_name(self):
        ScannerRun.objects.create(scan=self.scan, scanner="website")
        ScannerRun.objects.create(scan=self.scan, scanner="ssl")
        self.assertEqual(self.scan.scanner_runs.count(), 2)


# ═══════════════════════════════════════════════════
# Finding model tests
# ═══════════════════════════════════════════════════

class FindingModelTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.website = make_website(self.user)
        self.scan = make_scan(self.website)
        self.run = ScannerRun.objects.create(scan=self.scan, scanner="nmap")

    def test_create_finding(self):
        f = Finding.objects.create(
            scanner_run=self.run,
            category="security",
            check_code="nmap.open_port.22",
            title="Port 22 open (SSH)",
            severity=Finding.Severity.MEDIUM,
            status=Finding.Status.WARNING,
            recommendation="Restrict SSH access to VPN.",
        )
        self.assertEqual(f.severity, "medium")
        self.assertEqual(f.status, "warning")

    def test_finding_defaults(self):
        f = Finding.objects.create(
            scanner_run=self.run,
            category="ssl",
            check_code="ssl.overall",
            title="SSL checked",
        )
        self.assertEqual(f.severity, Finding.Severity.INFO)
        self.assertEqual(f.status, Finding.Status.UNKNOWN)
        self.assertEqual(f.evidence, {})
        self.assertEqual(f.recommendation, "")

    def test_findings_related_name(self):
        Finding.objects.create(
            scanner_run=self.run,
            category="security",
            check_code="nmap.open_port.80",
            title="Port 80 open",
        )
        Finding.objects.create(
            scanner_run=self.run,
            category="security",
            check_code="nmap.open_port.443",
            title="Port 443 open",
        )
        self.assertEqual(self.run.findings.count(), 2)


# ═══════════════════════════════════════════════════
# New Scan fields
# ═══════════════════════════════════════════════════

class ScanNewFieldsTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.website = make_website(self.user)

    def test_scan_type_defaults_to_health(self):
        scan = Scan.objects.create(website=self.website)
        self.assertEqual(scan.scan_type, Scan.ScanType.HEALTH)

    def test_scan_type_choices(self):
        for scan_type in [Scan.ScanType.HEALTH, Scan.ScanType.SECURITY, Scan.ScanType.FULL]:
            scan = Scan.objects.create(website=self.website, scan_type=scan_type)
            self.assertEqual(scan.scan_type, scan_type)

    def test_progress_defaults_to_zero(self):
        scan = Scan.objects.create(website=self.website)
        self.assertEqual(scan.progress, 0)

    def test_current_step_defaults_empty(self):
        scan = Scan.objects.create(website=self.website)
        self.assertEqual(scan.current_step, "")

    def test_steps_defaults_empty_list(self):
        scan = Scan.objects.create(website=self.website)
        self.assertEqual(scan.steps, [])

    def test_update_progress(self):
        scan = Scan.objects.create(website=self.website)
        scan.update_progress(45, current_step="SSL Check")
        scan.refresh_from_db()
        self.assertEqual(scan.progress, 45)
        self.assertEqual(scan.current_step, "SSL Check")

    def test_update_step(self):
        scan = Scan.objects.create(website=self.website)
        scan.steps = [{"key": "ssl", "status": "pending", "progress": 0}]
        scan.save()
        scan.update_step("ssl", status="completed", progress=100)
        scan.refresh_from_db()
        ssl_step = next(s for s in scan.steps if s["key"] == "ssl")
        self.assertEqual(ssl_step["status"], "completed")
        self.assertEqual(ssl_step["progress"], 100)

    def test_is_active_true_when_queued(self):
        scan = Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)
        self.assertTrue(scan.is_active)

    def test_is_active_true_when_running(self):
        scan = Scan.objects.create(website=self.website, status=Scan.Status.RUNNING)
        self.assertTrue(scan.is_active)

    def test_is_active_false_when_completed(self):
        scan = Scan.objects.create(website=self.website, status=Scan.Status.COMPLETED)
        self.assertFalse(scan.is_active)

    def test_duration_seconds(self):
        from django.utils import timezone
        from datetime import timedelta
        scan = Scan.objects.create(website=self.website, status=Scan.Status.RUNNING)
        now = timezone.now()
        scan.started_at = now - timedelta(seconds=30)
        scan.completed_at = now
        # duration_seconds uses in-memory values
        self.assertEqual(scan.duration_seconds, 30)

    def test_cancelled_status_added(self):
        scan = Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)
        scan.transition_to(Scan.Status.CANCELLED)
        self.assertEqual(scan.status, Scan.Status.CANCELLED)


# ═══════════════════════════════════════════════════
# Steps builder tests
# ═══════════════════════════════════════════════════

class StepsBuilderTests(TestCase):
    def test_health_steps_contains_core_scanners(self):
        steps = build_initial_steps("health")
        keys = [s["key"] for s in steps]
        for expected in ["website", "ssl", "dns", "email_security", "security_headers", "performance"]:
            self.assertIn(expected, keys)

    def test_security_steps_contains_external_tools(self):
        steps = build_initial_steps("security")
        keys = [s["key"] for s in steps]
        for expected in ["nmap", "nikto", "nuclei"]:
            self.assertIn(expected, keys)

    def test_full_steps_combines_health_and_security(self):
        steps = build_initial_steps("full")
        keys = [s["key"] for s in steps]
        # Must contain both internal and external
        self.assertIn("website", keys)
        self.assertIn("nmap", keys)

    def test_unknown_scan_type_defaults_to_health(self):
        steps = build_initial_steps("unknown_type")
        keys = [s["key"] for s in steps]
        self.assertIn("website", keys)
        self.assertNotIn("nmap", keys)

    def test_all_steps_start_pending(self):
        steps = build_initial_steps("health")
        for step in steps:
            self.assertEqual(step["status"], StepStatus.PENDING)
            self.assertEqual(step["progress"], 0)

    def test_compute_overall_progress_empty(self):
        self.assertEqual(compute_overall_progress([]), 0)

    def test_compute_overall_progress_all_pending(self):
        steps = build_initial_steps("health")
        self.assertEqual(compute_overall_progress(steps), 0)

    def test_compute_overall_progress_all_completed(self):
        steps = build_initial_steps("health")
        for s in steps:
            s["status"] = StepStatus.COMPLETED
            s["progress"] = 100
        self.assertEqual(compute_overall_progress(steps), 100)

    def test_compute_overall_progress_partial(self):
        steps = [
            {"key": "a", "weight": 50, "status": StepStatus.COMPLETED, "progress": 100},
            {"key": "b", "weight": 50, "status": StepStatus.PENDING, "progress": 0},
        ]
        # (50*100 + 50*0) / 100 = 50
        self.assertEqual(compute_overall_progress(steps), 50)

    def test_compute_overall_progress_running_step(self):
        steps = [
            {"key": "a", "weight": 100, "status": StepStatus.RUNNING, "progress": 60},
        ]
        self.assertEqual(compute_overall_progress(steps), 60)

    def test_failed_step_counts_as_complete_for_progress(self):
        steps = [
            {"key": "a", "weight": 50, "status": StepStatus.FAILED, "progress": 100},
            {"key": "b", "weight": 50, "status": StepStatus.PENDING, "progress": 0},
        ]
        self.assertEqual(compute_overall_progress(steps), 50)


# ═══════════════════════════════════════════════════
# Scanner Registry tests
# ═══════════════════════════════════════════════════

class ScannerRegistryTests(TestCase):
    def test_registry_can_retrieve_internal_scanners(self):
        from scanners.registry import ScannerRegistry
        # These must be registered after import
        import scanners  # noqa: F401 - triggers registration
        for name in ["website", "ssl", "dns", "email_security", "security_headers", "performance"]:
            scanner = ScannerRegistry.get(name)
            self.assertEqual(scanner.name, name)

    def test_registry_raises_key_error_for_unknown_scanner(self):
        from scanners.registry import ScannerRegistry
        with self.assertRaises(KeyError):
            ScannerRegistry.get("does_not_exist_xyz")

    def test_registry_list_contains_all_registered_scanners(self):
        from scanners.registry import ScannerRegistry
        import scanners  # noqa: F401
        all_scanners = ScannerRegistry.all()
        names = [s.name for s in all_scanners]
        for expected in ["website", "ssl", "dns", "nmap", "nikto"]:
            self.assertIn(expected, names)

    def test_internal_scanners_always_available(self):
        from scanners.registry import ScannerRegistry
        import scanners  # noqa: F401
        for name in ["website", "ssl", "dns", "email_security", "security_headers", "performance"]:
            scanner = ScannerRegistry.get(name)
            self.assertTrue(scanner.is_available(), f"{name} should always be available")


# ═══════════════════════════════════════════════════
# Orchestrator lifecycle tests (mocked scanners)
# ═══════════════════════════════════════════════════

class OrchestratorLifecycleTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.website = make_website(self.user)

    def _make_mock_scanner(self, name, available=True, raises=None):
        """Return a mock scanner for the registry."""
        mock = MagicMock()
        mock.name = name
        mock.is_available.return_value = available
        mock.timeout = 30
        if raises:
            mock.scan.side_effect = raises
            mock.scan_findings.side_effect = raises
        else:
            mock.scan.return_value = ScanResult(
                score=20, status="healthy", message="OK", details={}, recommendation=""
            )
            mock.scan_findings.return_value = [
                NormalizedFinding(
                    check_code=f"{name}.overall",
                    category=name,
                    severity=Severity.INFO,
                    status=FindingStatus.PASS,
                    title="OK",
                )
            ]
        return mock

    @patch("scanners.registry.ScannerRegistry")
    def test_orchestrator_transitions_to_running(self, mock_registry):
        mock_registry.get.return_value = self._make_mock_scanner("website")
        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.QUEUED,
            scan_type=Scan.ScanType.HEALTH,
        )
        from scans.services.orchestrator import ScanOrchestrator
        with patch.object(ScanOrchestrator, "_run_all_steps"):
            orchestrator = ScanOrchestrator(scan_id=scan.id)
            orchestrator.run()
        scan.refresh_from_db()
        # After run(), it should be COMPLETED
        self.assertIn(scan.status, [Scan.Status.COMPLETED, Scan.Status.RUNNING])

    @patch("scanners.registry.ScannerRegistry")
    def test_orchestrator_creates_scanner_runs(self, mock_registry):
        """Each step should create exactly one ScannerRun."""
        website_scanner = self._make_mock_scanner("website")
        ssl_scanner = self._make_mock_scanner("ssl")

        def get_scanner(name):
            return {"website": website_scanner, "ssl": ssl_scanner}[name]

        mock_registry.get.side_effect = get_scanner

        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.QUEUED,
            scan_type=Scan.ScanType.HEALTH,
        )
        # Patch steps to only 2 steps for speed
        from scans.services.steps_builder import build_initial_steps
        with patch("scans.services.steps_builder.build_initial_steps") as mock_steps, \
             patch("scans.services.scoring.recalculate_scan_health"):
            mock_steps.return_value = [
                {"key": "website", "label": "Website", "scanner": "website",
                 "weight": 50, "status": "pending", "progress": 0},
                {"key": "ssl", "label": "SSL", "scanner": "ssl",
                 "weight": 50, "status": "pending", "progress": 0},
            ]
            from scans.services.orchestrator import ScanOrchestrator
            ScanOrchestrator(scan_id=scan.id).run()

        self.assertEqual(ScannerRun.objects.filter(scan=scan).count(), 2)

    @patch("scanners.registry.ScannerRegistry")
    def test_scanner_failure_does_not_abort_scan(self, mock_registry):
        """A crashing scanner should mark its step FAILED but the scan continues."""
        failing_scanner = self._make_mock_scanner(
            "website", raises=RuntimeError("Connection refused")
        )
        passing_scanner = self._make_mock_scanner("ssl")

        def get_scanner(name):
            return {"website": failing_scanner, "ssl": passing_scanner}[name]

        mock_registry.get.side_effect = get_scanner

        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.QUEUED,
            scan_type=Scan.ScanType.HEALTH,
        )
        with patch("scans.services.steps_builder.build_initial_steps") as mock_steps, \
             patch("scans.services.scoring.recalculate_scan_health"):
            mock_steps.return_value = [
                {"key": "website", "label": "Website", "scanner": "website",
                 "weight": 50, "status": "pending", "progress": 0},
                {"key": "ssl", "label": "SSL", "scanner": "ssl",
                 "weight": 50, "status": "pending", "progress": 0},
            ]
            from scans.services.orchestrator import ScanOrchestrator
            ScanOrchestrator(scan_id=scan.id).run()

        scan.refresh_from_db()
        # Scan should complete despite website scanner failure
        self.assertEqual(scan.status, Scan.Status.COMPLETED)
        # Both scanner runs should exist
        runs = {r.scanner: r for r in ScannerRun.objects.filter(scan=scan)}
        self.assertEqual(runs["website"].status, "failed")
        self.assertEqual(runs["ssl"].status, "completed")

    @patch("scanners.registry.ScannerRegistry")
    def test_unavailable_scanner_marks_step_unavailable(self, mock_registry):
        """An unavailable scanner (binary missing) should mark step as UNAVAILABLE."""
        unavailable = self._make_mock_scanner("nmap", available=False)
        mock_registry.get.return_value = unavailable

        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.QUEUED,
            scan_type=Scan.ScanType.SECURITY,
        )
        with patch("scans.services.steps_builder.build_initial_steps") as mock_steps, \
             patch("scans.services.scoring.recalculate_scan_health"):
            mock_steps.return_value = [
                {"key": "nmap", "label": "Nmap", "scanner": "nmap",
                 "weight": 100, "status": "pending", "progress": 0},
            ]
            from scans.services.orchestrator import ScanOrchestrator
            ScanOrchestrator(scan_id=scan.id).run()

        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.COMPLETED)
        run = ScannerRun.objects.get(scan=scan, scanner="nmap")
        self.assertEqual(run.status, "unavailable")
        # Step should be marked unavailable
        nmap_step = next(s for s in scan.steps if s["key"] == "nmap")
        self.assertEqual(nmap_step["status"], StepStatus.UNAVAILABLE)

    @patch("scanners.registry.ScannerRegistry")
    def test_progress_updates_through_lifecycle(self, mock_registry):
        mock_registry.get.return_value = self._make_mock_scanner("website")

        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.QUEUED,
            scan_type=Scan.ScanType.HEALTH,
        )
        with patch("scans.services.steps_builder.build_initial_steps") as mock_steps, \
             patch("scans.services.scoring.recalculate_scan_health"):
            mock_steps.return_value = [
                {"key": "website", "label": "Website", "scanner": "website",
                 "weight": 100, "status": "pending", "progress": 0},
            ]
            from scans.services.orchestrator import ScanOrchestrator
            ScanOrchestrator(scan_id=scan.id).run()

        scan.refresh_from_db()
        self.assertEqual(scan.progress, 100)

    def test_orchestrator_handles_nonexistent_scan_gracefully(self):
        from scans.services.orchestrator import ScanOrchestrator
        # Should not raise
        ScanOrchestrator(scan_id=999999).run()

    def test_orchestrator_skips_already_completed_scan(self):
        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.COMPLETED,
        )
        with patch("scans.services.steps_builder.build_initial_steps") as mock_steps:
            from scans.services.orchestrator import ScanOrchestrator
            ScanOrchestrator(scan_id=scan.id).run()
            mock_steps.assert_not_called()

    @patch("scanners.registry.ScannerRegistry")
    def test_cancellation_stops_further_steps(self, mock_registry):
        """If scan is cancelled mid-run, remaining steps should be skipped."""
        call_count = {"n": 0}

        def get_scanner(name):
            call_count["n"] += 1
            s = self._make_mock_scanner(name)
            # After first scanner runs, cancel the scan
            if call_count["n"] == 1:
                Scan.objects.filter(pk=self.scan_ref[0]).update(
                    status=Scan.Status.CANCELLED
                )
            return s

        mock_registry.get.side_effect = get_scanner

        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.QUEUED,
        )
        self.scan_ref = [scan.id]

        with patch("scans.services.steps_builder.build_initial_steps") as mock_steps, \
             patch("scans.services.scoring.recalculate_scan_health"):
            mock_steps.return_value = [
                {"key": "website", "label": "Website", "scanner": "website",
                 "weight": 50, "status": "pending", "progress": 0},
                {"key": "ssl", "label": "SSL", "scanner": "ssl",
                 "weight": 50, "status": "pending", "progress": 0},
                {"key": "dns", "label": "DNS", "scanner": "dns",
                 "weight": 50, "status": "pending", "progress": 0},
            ]
            from scans.services.orchestrator import ScanOrchestrator
            ScanOrchestrator(scan_id=scan.id).run()

        # Only the first scanner run should have been created
        runs_count = ScannerRun.objects.filter(scan=scan).count()
        self.assertLessEqual(runs_count, 2)  # At most website + ssl

    @patch("scanners.registry.ScannerRegistry")
    def test_findings_persisted_correctly(self, mock_registry):
        findings_to_return = [
            NormalizedFinding(
                check_code="ssl.cert_valid",
                category="ssl",
                severity=Severity.INFO,
                status=FindingStatus.PASS,
                title="Certificate valid",
                recommendation="Renew before expiry.",
            ),
            NormalizedFinding(
                check_code="ssl.cert_expiry",
                category="ssl",
                severity=Severity.MEDIUM,
                status=FindingStatus.WARNING,
                title="Certificate expires in 20 days",
            ),
        ]
        ssl_scanner = self._make_mock_scanner("ssl")
        ssl_scanner.scan_findings.return_value = findings_to_return
        mock_registry.get.return_value = ssl_scanner

        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.QUEUED,
        )
        with patch("scans.services.steps_builder.build_initial_steps") as mock_steps, \
             patch("scans.services.scoring.recalculate_scan_health"):
            mock_steps.return_value = [
                {"key": "ssl", "label": "SSL", "scanner": "ssl",
                 "weight": 100, "status": "pending", "progress": 0},
            ]
            from scans.services.orchestrator import ScanOrchestrator
            ScanOrchestrator(scan_id=scan.id).run()

        self.assertEqual(Finding.objects.filter(scanner_run__scan=scan).count(), 2)
        finding = Finding.objects.get(check_code="ssl.cert_expiry", scanner_run__scan=scan)
        self.assertEqual(finding.severity, "medium")
        self.assertEqual(finding.status, "warning")


# ═══════════════════════════════════════════════════
# End-to-end scoring pipeline tests (scoring NOT mocked)
# ═══════════════════════════════════════════════════

class ScoringPipelineE2ETests(TestCase):
    """Full scanner → ScannerRun.metadata → CheckResult → health_score pipeline.

    Only the external scanner behaviour is stubbed (deterministic ScanResults);
    ``calculate_health_score`` and ``recalculate_scan_health`` run for real.
    """

    SCENARIO = {
        "website": (20, "healthy"),
        "ssl": (16, "healthy"),
        "dns": (15, "healthy"),
        "email_security": (15, "healthy"),
        "security_headers": (0, "critical"),
        "performance": (15, "healthy"),
        "uptime": (None, "healthy"),
    }

    def setUp(self):
        self.user = make_user()
        self.website = make_website(self.user)

    def _make_deterministic_scanner(self, name, score, status_str):
        mock = MagicMock()
        mock.name = name
        mock.is_available.return_value = True
        mock.timeout = 30
        mock.scan.return_value = ScanResult(
            score=score,
            status=status_str,
            message=f"{name} result",
            details={},
            recommendation="",
        )
        mock.scan_findings.return_value = [
            NormalizedFinding(
                check_code=f"{name}.overall",
                category=name,
                severity=Severity.INFO,
                status=FindingStatus.PASS,
                title=f"{name} ok",
            )
        ]
        return mock

    @patch("scanners.registry.ScannerRegistry")
    def test_full_pipeline_health_score_81_critical(self, mock_registry):
        """Deterministic 7-scanner run must yield health_score=81, status=critical."""

        def get_scanner(name):
            score, status_str = self.SCENARIO[name]
            return self._make_deterministic_scanner(name, score, status_str)

        mock_registry.get.side_effect = get_scanner

        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.QUEUED,
            scan_type=Scan.ScanType.HEALTH,
        )

        from scans.services.orchestrator import ScanOrchestrator
        # NOTE: recalculate_scan_health / calculate_health_score are NOT mocked here.
        ScanOrchestrator(scan_id=scan.id).run()

        # ── A. Scan final ──
        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.COMPLETED)
        self.assertEqual(scan.health_score, 81)
        self.assertEqual(scan.health_status, HealthStatus.CRITICAL)

        # ── B. ScannerRun created + metadata scores ──
        runs = {r.scanner: r for r in ScannerRun.objects.filter(scan=scan)}
        self.assertEqual(len(runs), len(self.SCENARIO))
        for name, (score, _status) in self.SCENARIO.items():
            with self.subTest(scanner=name):
                self.assertEqual(runs[name].status, "completed")
                self.assertEqual(runs[name].metadata["score"], score)
                self.assertEqual(runs[name].metadata["findings_count"], 1)

        # ── C. CheckResult with expected scores (uptime excluded) ──
        results = {cr.category: cr for cr in CheckResult.objects.filter(scan=scan)}
        expected_scores = {
            "website": 20,
            "ssl": 16,
            "dns": 15,
            "email_security": 15,
            "security_headers": 0,
            "performance": 15,
            "uptime": None,
        }
        self.assertEqual(len(results), len(expected_scores))
        for category, score in expected_scores.items():
            with self.subTest(category=category):
                self.assertEqual(results[category].score, score)

        # ── D. Provenance: stored value == live calculate_health_score() ──
        from scans.services.scoring import calculate_health_score
        recomputed = calculate_health_score(scan.check_results.all())
        self.assertEqual(recomputed.score, 81)
        self.assertEqual(recomputed.status, HealthStatus.CRITICAL)
        self.assertEqual(scan.health_score, recomputed.score)

        # ── E. Uptime is NOT part of the weighted score ──
        from scans.services.scoring import CHECK_WEIGHTS
        self.assertNotIn("uptime", CHECK_WEIGHTS)


# ═══════════════════════════════════════════════════
# Recommendation engine tests
# ═══════════════════════════════════════════════════

class RecommendationEngineTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.website = make_website(self.user)
        self.scan = make_scan(self.website)

    def _add_check_result(self, category, score, result_status, recommendation="Fix this."):
        return CheckResult.objects.create(
            scan=self.scan,
            category=category,
            score=score,
            status=result_status,
            summary="Summary",
            recommendation=recommendation,
        )

    def test_recommendations_from_check_results(self):
        self._add_check_result(CheckResult.Category.SSL, 10, HealthStatus.WARNING)
        engine = RecommendationEngine(self.scan)
        recs = engine.generate()
        categories = [r.category for r in recs]
        self.assertIn("ssl", categories)

    def test_no_recommendations_for_healthy_checks(self):
        self._add_check_result(CheckResult.Category.SSL, 20, HealthStatus.HEALTHY)
        self._add_check_result(CheckResult.Category.DNS, 15, HealthStatus.HEALTHY)
        engine = RecommendationEngine(self.scan)
        recs = engine.generate()
        # Healthy results with recommendations still present (if not "")
        # But since we have recommendation="Fix this.", they appear
        # The engine should NOT suppress recs for healthy checks with non-empty recommendation
        # But our engine only includes non-healthy ones from check_results
        # (status != 'healthy')
        self.assertEqual(len(recs), 0)

    def test_recommendations_sorted_by_priority(self):
        self._add_check_result(CheckResult.Category.SSL, 0, HealthStatus.CRITICAL)
        self._add_check_result(CheckResult.Category.DNS, 10, HealthStatus.WARNING)
        engine = RecommendationEngine(self.scan)
        recs = engine.generate()
        self.assertGreaterEqual(len(recs), 2)
        # Critical comes before warning
        priorities = [r.priority for r in recs]
        self.assertEqual(priorities, sorted(priorities))

    def test_recommendation_from_findings(self):
        run = ScannerRun.objects.create(scan=self.scan, scanner="nmap")
        run.start()
        Finding.objects.create(
            scanner_run=run,
            category="security",
            check_code="nmap.open_port.22",
            title="Port 22 open",
            severity="high",
            status="fail",
            recommendation="Close SSH port or restrict to VPN.",
        )
        engine = RecommendationEngine(self.scan)
        recs = engine.generate()
        self.assertTrue(any("Port 22" in r.title for r in recs))

    def test_to_dict_list_returns_serializable(self):
        self._add_check_result(CheckResult.Category.SSL, 5, HealthStatus.WARNING)
        engine = RecommendationEngine(self.scan)
        result = engine.to_dict_list()
        self.assertIsInstance(result, list)
        if result:
            self.assertIn("title", result[0])
            self.assertIn("priority", result[0])
            self.assertIn("action", result[0])

    def test_deduplication_keeps_highest_priority(self):
        """Same check_code from both findings and check_results → keep highest priority."""
        self._add_check_result(CheckResult.Category.SSL, 0, HealthStatus.CRITICAL)
        run = ScannerRun.objects.create(scan=self.scan, scanner="ssl")
        Finding.objects.create(
            scanner_run=run,
            category="ssl",
            check_code="ssl.overall",
            title="SSL critical issue",
            severity="critical",
            status="fail",
            recommendation="Fix SSL configuration.",
        )
        engine = RecommendationEngine(self.scan)
        recs = engine.generate()
        ssl_recs = [r for r in recs if "ssl" in r.check_code]
        # Should be deduplicated
        codes = [r.check_code for r in ssl_recs]
        self.assertEqual(len(codes), len(set(codes)))


# ═══════════════════════════════════════════════════
# Website scan API tests (trigger_scan + active_scan)
# ═══════════════════════════════════════════════════

@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class WebsiteScanAPITests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.other_user = make_user("other@example.com")
        self.website = make_website(self.user)
        self.other_website = make_website(self.other_user, "other.example")
        auth_client(self.client, self.user)

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_trigger_scan_creates_queued_scan(self, mock_delay):
        response = self.client.post(f"/api/v1/websites/{self.website.id}/scan/")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["status"], "queued")
        scan = Scan.objects.get(id=response.data["id"])
        self.assertEqual(scan.scan_type, Scan.ScanType.HEALTH)
        mock_delay.assert_called_once_with(scan.id)

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_trigger_scan_with_health_type(self, mock_delay):
        response = self.client.post(
            f"/api/v1/websites/{self.website.id}/scan/",
            {"scan_type": "health"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["scan_type"], "health")

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_trigger_scan_with_security_type(self, mock_delay):
        response = self.client.post(
            f"/api/v1/websites/{self.website.id}/scan/",
            {"scan_type": "security"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["scan_type"], "security")

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_trigger_scan_with_full_type(self, mock_delay):
        response = self.client.post(
            f"/api/v1/websites/{self.website.id}/scan/",
            {"scan_type": "full"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["scan_type"], "full")

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_trigger_scan_invalid_type_returns_400(self, mock_delay):
        response = self.client.post(
            f"/api/v1/websites/{self.website.id}/scan/",
            {"scan_type": "invalid_type"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_delay.assert_not_called()

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_trigger_scan_omitted_type_defaults_to_health(self, mock_delay):
        """Backward compat: no scan_type → health."""
        response = self.client.post(f"/api/v1/websites/{self.website.id}/scan/")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["scan_type"], "health")

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_duplicate_active_scan_returns_409(self, mock_delay):
        Scan.objects.create(website=self.website, status=Scan.Status.RUNNING)
        response = self.client.post(f"/api/v1/websites/{self.website.id}/scan/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("scan_already_running", response.data)
        self.assertTrue(response.data["scan_already_running"])
        mock_delay.assert_not_called()

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_queued_scan_also_blocks_new_scan(self, mock_delay):
        Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)
        response = self.client.post(f"/api/v1/websites/{self.website.id}/scan/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_completed_scan_allows_new_scan(self, mock_delay):
        Scan.objects.create(website=self.website, status=Scan.Status.COMPLETED)
        response = self.client.post(f"/api/v1/websites/{self.website.id}/scan/")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_trigger_scan_other_users_website_returns_404(self):
        response = self.client.post(f"/api/v1/websites/{self.other_website.id}/scan/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_trigger_scan_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.post(f"/api/v1/websites/{self.website.id}/scan/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_active_scan_returns_running_scan(self, mock_delay):
        scan = Scan.objects.create(website=self.website, status=Scan.Status.RUNNING)
        response = self.client.get(f"/api/v1/websites/{self.website.id}/active_scan/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], scan.id)
        self.assertEqual(response.data["status"], "running")

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_active_scan_returns_queued_scan(self, mock_delay):
        scan = Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)
        response = self.client.get(f"/api/v1/websites/{self.website.id}/active_scan/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], scan.id)

    def test_active_scan_no_active_returns_404(self):
        Scan.objects.create(website=self.website, status=Scan.Status.COMPLETED)
        response = self.client.get(f"/api/v1/websites/{self.website.id}/active_scan/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_active_scan_includes_progress_fields(self):
        Scan.objects.create(
            website=self.website,
            status=Scan.Status.RUNNING,
            progress=35,
            current_step="SSL Check",
        )
        response = self.client.get(f"/api/v1/websites/{self.website.id}/active_scan/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["progress"], 35)
        self.assertEqual(response.data["current_step"], "SSL Check")

    def test_active_scan_other_user_website_returns_404(self):
        Scan.objects.create(website=self.other_website, status=Scan.Status.RUNNING)
        response = self.client.get(f"/api/v1/websites/{self.other_website.id}/active_scan/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ═══════════════════════════════════════════════════
# Scan API sub-endpoints (scanner-runs, findings, recs)
# ═══════════════════════════════════════════════════

@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ScanSubEndpointTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.other_user = make_user("other@example.com")
        self.website = make_website(self.user)
        self.scan = make_scan(self.website, status=Scan.Status.COMPLETED)
        self.run = ScannerRun.objects.create(scan=self.scan, scanner="ssl")
        self.run.start()
        self.run.finish(status="completed", metadata={"findings_count": 2})
        self.finding = Finding.objects.create(
            scanner_run=self.run,
            category="ssl",
            check_code="ssl.cert_valid",
            title="Certificate valid",
            severity="info",
            status="pass",
        )
        self.other_website = make_website(self.other_user, "other.example")
        self.other_scan = make_scan(self.other_website)
        auth_client(self.client, self.user)

    # ── scanner-runs ──

    def test_scanner_runs_endpoint_returns_runs(self):
        response = self.client.get(f"/api/v1/scans/{self.scan.id}/scanner-runs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["scanner"], "ssl")
        self.assertEqual(response.data[0]["status"], "completed")

    def test_scanner_runs_does_not_expose_other_users(self):
        response = self.client.get(f"/api/v1/scans/{self.other_scan.id}/scanner-runs/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_scanner_runs_no_raw_output_in_response(self):
        response = self.client.get(f"/api/v1/scans/{self.scan.id}/scanner-runs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("raw_output", response.data[0])

    # ── findings ──

    def test_findings_endpoint_returns_findings(self):
        response = self.client.get(f"/api/v1/scans/{self.scan.id}/findings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["check_code"], "ssl.cert_valid")
        self.assertEqual(response.data[0]["scanner"], "ssl")

    def test_findings_filter_by_severity(self):
        Finding.objects.create(
            scanner_run=self.run,
            category="security",
            check_code="nmap.open_port.22",
            title="SSH open",
            severity="high",
            status="warning",
        )
        response = self.client.get(f"/api/v1/scans/{self.scan.id}/findings/?severity=high")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["severity"], "high")

    def test_findings_filter_by_category(self):
        response = self.client.get(f"/api/v1/scans/{self.scan.id}/findings/?category=ssl")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_findings_filter_by_status(self):
        response = self.client.get(f"/api/v1/scans/{self.scan.id}/findings/?status=pass")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_findings_does_not_expose_other_users(self):
        response = self.client.get(f"/api/v1/scans/{self.other_scan.id}/findings/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ── recommendations ──

    def test_recommendations_endpoint(self):
        response = self.client.get(f"/api/v1/scans/{self.scan.id}/recommendations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("recommendations", response.data)
        self.assertIsInstance(response.data["recommendations"], list)

    def test_recommendations_does_not_expose_other_users(self):
        response = self.client.get(f"/api/v1/scans/{self.other_scan.id}/recommendations/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ═══════════════════════════════════════════════════
# Scan list filtering tests
# ═══════════════════════════════════════════════════

@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ScanListFilterTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.website = make_website(self.user)
        self.website2 = make_website(self.user, "second.example")
        self.scan_health = make_scan(
            self.website,
            status=Scan.Status.COMPLETED,
            scan_type=Scan.ScanType.HEALTH,
        )
        self.scan_security = make_scan(
            self.website,
            status=Scan.Status.RUNNING,
            scan_type=Scan.ScanType.SECURITY,
        )
        self.scan_w2 = make_scan(
            self.website2,
            status=Scan.Status.COMPLETED,
            scan_type=Scan.ScanType.HEALTH,
        )
        auth_client(self.client, self.user)

    def test_filter_by_website(self):
        response = self.client.get(f"/api/v1/scans/?website={self.website.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertIn(self.scan_health.id, ids)
        self.assertIn(self.scan_security.id, ids)
        self.assertNotIn(self.scan_w2.id, ids)

    def test_filter_by_status(self):
        response = self.client.get("/api/v1/scans/?status=completed")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        statuses = [item["status"] for item in response.data["results"]]
        self.assertTrue(all(s == "completed" for s in statuses))

    def test_filter_by_scan_type(self):
        response = self.client.get("/api/v1/scans/?scan_type=security")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        types = [item["scan_type"] for item in response.data["results"]]
        self.assertTrue(all(t == "security" for t in types))

    def test_filter_combined(self):
        response = self.client.get(
            f"/api/v1/scans/?website={self.website.id}&status=completed&scan_type=health"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.scan_health.id])

    def test_scan_list_uses_lightweight_serializer(self):
        """List endpoint should NOT include nested check_results."""
        response = self.client.get("/api/v1/scans/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if response.data["results"]:
            self.assertNotIn("check_results", response.data["results"][0])

    def test_scan_detail_includes_check_results(self):
        response = self.client.get(f"/api/v1/scans/{self.scan_health.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("check_results", response.data)

    def test_scan_detail_includes_new_fields(self):
        response = self.client.get(f"/api/v1/scans/{self.scan_health.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for field in ["scan_type", "progress", "current_step", "steps", "is_active"]:
            self.assertIn(field, response.data)
