"""Lighthouse adapter tests — execution is always mocked.

The real Lighthouse/Chromium binary is never started: the sandbox executor is
replaced by a ``MagicMock`` so the tests are deterministic and fast while still
exercising the full command construction, parsing and normalisation paths.
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from scanners.base import FindingStatus, ScanContext, Severity
from scanners.exceptions import TargetValidationError
from scanners.executors.command import CommandResult
from scanners.executors.sandbox import SandboxLimits, SandboxMode
from scanners.implementations.lighthouse import LighthouseScanner
from scanners.parsers.lighthouse import parse_lighthouse_json
from scanners.security.target_validator import TargetInfo


LIGHTHOUSE_REPORT = {
    "lighthouseVersion": "12.6.0",
    "requestedUrl": "https://example.com",
    "finalUrl": "https://example.com/",
    "fetchTime": "2026-10-24T09:00:00.000Z",
    "userAgent": "Mozilla/5.0 HeadlessChrome",
    "categories": {
        "performance": {
            "id": "performance",
            "score": 0.87,
            "auditRefs": [
                {"id": "first-contentful-paint", "weight": 10},
                {"id": "largest-contentful-paint", "weight": 25},
                {"id": "total-blocking-time", "weight": 30},
                {"id": "cumulative-layout-shift", "weight": 25},
                {"id": "speed-index", "weight": 10},
                {"id": "server-response-time", "weight": 0},
                {"id": "total-byte-weight", "weight": 0},
                {"id": "render-blocking-resources", "weight": 0},
                {"id": "unused-css-rules", "weight": 0},
            ],
        },
        "seo": {
            "id": "seo",
            "score": 1.0,
            "auditRefs": [
                {"id": "is-crawlable", "weight": 1},
                {"id": "document-title", "weight": 1},
                {"id": "meta-description", "weight": 1},
            ],
        },
        "accessibility": {
            "id": "accessibility",
            "score": 0.90,
            "auditRefs": [{"id": "color-contrast", "weight": 1}],
        },
    },
    "audits": {
        "first-contentful-paint": {
            "id": "first-contentful-paint",
            "title": "First Contentful Paint",
            "description": "FCP marks the time at which the first text or image is painted.",
            "score": 1.0,
            "scoreDisplayMode": "numeric",
            "displayValue": "1.2 s",
            "numericValue": 1200,
            "numericUnit": "millisecond",
        },
        "largest-contentful-paint": {
            "id": "largest-contentful-paint",
            "title": "Largest Contentful Paint",
            "description": "LCP marks the time at which the largest text or image is painted.",
            "score": 0.4,
            "scoreDisplayMode": "numeric",
            "displayValue": "5.2 s",
            "numericValue": 5200,
            "numericUnit": "millisecond",
        },
        "total-blocking-time": {
            "id": "total-blocking-time",
            "title": "Total Blocking Time",
            "description": "Sum of all time periods between FCP and Time to Interactive.",
            "score": 1.0,
            "scoreDisplayMode": "numeric",
            "displayValue": "120 ms",
            "numericValue": 120,
            "numericUnit": "millisecond",
        },
        "cumulative-layout-shift": {
            "id": "cumulative-layout-shift",
            "title": "Cumulative Layout Shift",
            "description": "Measures unexpected layout shifts.",
            "score": 1.0,
            "scoreDisplayMode": "numeric",
            "displayValue": "0.05",
            "numericValue": 0.05,
            "numericUnit": "",
        },
        "speed-index": {
            "id": "speed-index",
            "title": "Speed Index",
            "description": "How quickly content is visibly populated.",
            "score": 1.0,
            "scoreDisplayMode": "numeric",
            "displayValue": "2.1 s",
            "numericValue": 2100,
            "numericUnit": "millisecond",
        },
        "server-response-time": {
            "id": "server-response-time",
            "title": "Initial server response time was short",
            "description": "Keep the server response time for the main document short.",
            "score": 0.7,
            "scoreDisplayMode": "numeric",
            "displayValue": "1.2 s",
            "numericValue": 1200,
            "numericUnit": "millisecond",
        },
        "total-byte-weight": {
            "id": "total-byte-weight",
            "title": "Avoid enormous network payloads",
            "description": "Large network payloads cost users real money and are correlated with long load times.",
            "score": 0.9,
            "scoreDisplayMode": "numeric",
            "displayValue": "1,800 KiB",
            "numericValue": 1_800_000,
            "numericUnit": "byte",
        },
        "render-blocking-resources": {
            "id": "render-blocking-resources",
            "title": "Eliminate render-blocking resources",
            "description": "Resources are blocking the first paint of your page.",
            "score": 0.2,
            "scoreDisplayMode": "numeric",
            "displayValue": "Potential savings of 800 ms",
            "numericValue": 800,
            "numericUnit": "millisecond",
        },
        "unused-css-rules": {
            "id": "unused-css-rules",
            "title": "Reduce unused CSS",
            "description": "Remove dead rules from stylesheets.",
            "score": 0.5,
            "scoreDisplayMode": "numeric",
            "displayValue": "Potential savings of 20 KiB",
            "numericValue": 20_000,
            "numericUnit": "byte",
        },
        "is-crawlable": {
            "id": "is-crawlable",
            "title": "Page isn't blocked from indexing",
            "description": "Search engines can index this page.",
            "score": 1.0,
            "scoreDisplayMode": "binary",
        },
        "document-title": {
            "id": "document-title",
            "title": "Document has a title element",
            "description": "The title gives screen reader users an overview of the page.",
            "score": 1.0,
            "scoreDisplayMode": "binary",
        },
        "meta-description": {
            "id": "meta-description",
            "title": "Document does not have a meta description",
            "description": "Meta descriptions may be included in search results to concisely describe page content.",
            "score": 0.0,
            "scoreDisplayMode": "binary",
        },
        "color-contrast": {
            "id": "color-contrast",
            "title": "Background and foreground colors have sufficient contrast",
            "description": "Low-contrast text is difficult to read.",
            "score": 0.0,
            "scoreDisplayMode": "binary",
        },
        "network-requests": {
            "id": "network-requests",
            "title": "Network Requests",
            "description": "Lists the network requests that were made during page load.",
            "score": 1.0,
            "scoreDisplayMode": "informative",
        },
        "errors-in-console": {
            "id": "errors-in-console",
            "title": "Browser errors were logged to the console",
            "description": "Errors logged to the console indicate unresolved problems.",
            "score": None,
            "scoreDisplayMode": "error",
        },
    },
    "runtimeError": None,
    "runWarnings": [],
}


def _target() -> TargetInfo:
    return TargetInfo(
        hostname="example.com",
        url="https://example.com",
        safe_ips=["93.184.216.34"],
        scheme="https",
    )


def _command_result(**overrides) -> CommandResult:
    payload = {
        "exit_code": 0,
        "stdout": json.dumps(LIGHTHOUSE_REPORT),
        "stderr": "",
        "duration_ms": 4200,
        "command": ["lighthouse"],
    }
    payload.update(overrides)
    return CommandResult(**payload)


# ═══════════════════════════════════════════════════
# Parser
# ═══════════════════════════════════════════════════


class LighthouseParserTests(SimpleTestCase):
    def test_parses_category_scores(self):
        report = parse_lighthouse_json(json.dumps(LIGHTHOUSE_REPORT))
        self.assertIsNotNone(report)
        self.assertEqual(report.percent_of("performance"), 87)
        self.assertEqual(report.percent_of("seo"), 100)
        self.assertIsNone(report.percent_of("best-practices"))
        self.assertEqual(report.lighthouse_version, "12.6.0")
        self.assertEqual(report.final_url, "https://example.com/")

    def test_skips_passing_non_core_audits(self):
        report = parse_lighthouse_json(json.dumps(LIGHTHOUSE_REPORT))
        ids = {audit.audit_id for audit in report.audits}
        self.assertIn("largest-contentful-paint", ids)
        self.assertIn("meta-description", ids)
        self.assertNotIn("is-crawlable", ids)  # passing binary audit
        self.assertNotIn("document-title", ids)  # passing binary audit
        self.assertNotIn("network-requests", ids)  # informative
        self.assertNotIn("errors-in-console", ids)  # error, no score
        self.assertNotIn("color-contrast", ids)  # category not requested

    def test_core_metrics_are_always_kept(self):
        report = parse_lighthouse_json(json.dumps(LIGHTHOUSE_REPORT))
        metrics = report.core_metrics()
        self.assertEqual(metrics["largest-contentful-paint"]["value"], 5200)
        self.assertEqual(metrics["cumulative-layout-shift"]["value"], 0.05)

    def test_unrequested_categories_are_ignored(self):
        report = parse_lighthouse_json(
            json.dumps(LIGHTHOUSE_REPORT), categories=["performance"]
        )
        self.assertNotIn("seo", report.category_scores)
        categories = {audit.category for audit in report.audits}
        self.assertNotIn("seo", categories)

    def test_tolerates_prefixed_noise(self):
        noisy = "Chromium warning: something\n" + json.dumps(LIGHTHOUSE_REPORT)
        report = parse_lighthouse_json(noisy)
        self.assertIsNotNone(report)
        self.assertEqual(report.percent_of("performance"), 87)

    def test_invalid_json_returns_none(self):
        self.assertIsNone(parse_lighthouse_json(""))
        self.assertIsNone(parse_lighthouse_json("not json at all"))
        self.assertIsNone(parse_lighthouse_json('{"broken": '))

    def test_runtime_error_is_exposed(self):
        payload = dict(LIGHTHOUSE_REPORT)
        payload["runtimeError"] = {
            "code": "NO_FCP",
            "message": "The page did not paint any content.",
        }
        report = parse_lighthouse_json(json.dumps(payload))
        self.assertEqual(report.runtime_error["code"], "NO_FCP")
        self.assertFalse(report.ok)

    def test_run_warnings_are_captured(self):
        payload = dict(LIGHTHOUSE_REPORT)
        payload["runWarnings"] = [
            "The page loaded too slowly to finish within the time limit."
        ]
        report = parse_lighthouse_json(json.dumps(payload))
        self.assertEqual(len(report.run_warnings), 1)


# ═══════════════════════════════════════════════════
# Scanner adapter (execution mocked)
# ═══════════════════════════════════════════════════


class LighthouseScannerTests(SimpleTestCase):
    def setUp(self):
        self.scanner = LighthouseScanner()
        self.executor = MagicMock()
        self.executor.mode = SandboxMode.PROCESS
        self.executor.is_available.return_value = True
        self.executor.limits_for.return_value = SandboxLimits(
            timeout_s=120,
            cpu_seconds=180,
            memory_mb=2048,
            file_size_mb=64,
            open_files=256,
        )
        self.executor.run.return_value = _command_result()

        self.patches = [
            patch(
                "scanners.implementations.lighthouse.shutil.which",
                return_value="/usr/local/bin/lighthouse",
            ),
            patch(
                "scanners.implementations.lighthouse.get_sandbox_executor",
                return_value=self.executor,
            ),
            patch(
                "scanners.implementations.lighthouse.validate_target",
                return_value=_target(),
            ),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    # ── Happy path ──

    def test_execute_returns_checkresult_compatible_result(self):
        outcome = self.scanner.execute("example.com")

        # performance 0.87 * 15 = 13.05 → 13 (CheckResult max is 15)
        self.assertEqual(outcome.result.score, 13)
        # Lighthouse grades 87/100 as "needs improvement" (>= 90 is green).
        self.assertEqual(outcome.result.status, "warning")
        self.assertLessEqual(outcome.result.score, 15)
        self.assertIn("Lighthouse performance 87/100", outcome.result.message)
        self.assertIn("LCP 5.2 s", outcome.result.message)
        self.assertEqual(outcome.result.details["category_scores"]["seo"], 100)

    def test_execute_runs_the_tool_exactly_once(self):
        self.scanner.execute("example.com")
        self.assertEqual(self.executor.run.call_count, 1)

    def test_findings_are_normalized_for_aka(self):
        outcome = self.scanner.execute("example.com")
        by_code = {finding.check_code: finding for finding in outcome.findings}

        self.assertIn("lighthouse.performance_score", by_code)
        self.assertIn("lighthouse.seo_score", by_code)
        self.assertIn("lighthouse.largest-contentful-paint", by_code)
        self.assertIn("lighthouse.meta-description", by_code)

        perf = by_code["lighthouse.performance_score"]
        self.assertEqual(perf.detected_value, 87)
        self.assertEqual(perf.category, "performance")
        self.assertEqual(perf.status, FindingStatus.WARNING)  # 87 < 90

        seo = by_code["lighthouse.seo_score"]
        self.assertEqual(seo.category, "seo")
        self.assertEqual(seo.status, FindingStatus.PASS)

        lcp = by_code["lighthouse.largest-contentful-paint"]
        self.assertEqual(lcp.severity, Severity.HIGH)
        self.assertEqual(lcp.status, FindingStatus.FAIL)
        self.assertEqual(lcp.detected_value, 5200)
        self.assertEqual(lcp.expected_value, "<= 2.5 s")
        self.assertEqual(lcp.evidence["category"], "performance")

        meta = by_code["lighthouse.meta-description"]
        self.assertEqual(meta.category, "seo")
        self.assertEqual(meta.severity, Severity.HIGH)

    def test_passing_core_metrics_are_reported_as_pass(self):
        outcome = self.scanner.execute("example.com")
        fcp = next(
            finding
            for finding in outcome.findings
            if finding.check_code == "lighthouse.first-contentful-paint"
        )
        self.assertEqual(fcp.status, FindingStatus.PASS)
        self.assertEqual(fcp.severity, Severity.INFO)

    def test_build_command_keeps_target_as_separate_argument(self):
        command = self.scanner.build_command(
            "https://example.com", {"target": _target()}
        )
        self.assertEqual(command[0], "lighthouse")
        self.assertEqual(command[1], "https://example.com")
        self.assertIn("--output=json", command)
        self.assertIn("--output-path=stdout", command)
        self.assertIn("--only-categories=performance,seo", command)
        chrome_flags = next(
            flag for flag in command if flag.startswith("--chrome-flags=")
        )
        self.assertIn("MAP example.com 93.184.216.34", chrome_flags)

    def test_timeout_is_clamped_by_scan_context(self):
        context = ScanContext(
            scan_id=1,
            domain="example.com",
            timeout=25,
            deadline_monotonic=time.monotonic() + 25.9,
            target=_target(),
        )
        self.scanner.execute("example.com", context=context)
        self.executor.limits_for.assert_called_once()
        self.assertEqual(self.executor.limits_for.call_args.kwargs["timeout"], 25)

    # ── Resource / failure paths ──

    def test_timeout_returns_zero_score_and_finding(self):
        self.executor.run.return_value = _command_result(
            exit_code=-1,
            stdout="",
            timed_out=True,
            killed_reason="timeout",
            duration_ms=120_000,
        )
        outcome = self.scanner.execute("example.com")

        self.assertEqual(outcome.result.score, 0)
        self.assertEqual(outcome.result.status, "warning")
        self.assertEqual(outcome.findings[0].check_code, "lighthouse.timeout")

    def test_memory_limit_returns_explicit_finding(self):
        self.executor.run.return_value = _command_result(
            exit_code=-9,
            stdout="",
            memory_exceeded=True,
            killed_reason="memory",
        )
        outcome = self.scanner.execute("example.com")
        self.assertEqual(outcome.result.score, 0)
        self.assertEqual(outcome.findings[0].check_code, "lighthouse.memory_limit")

    def test_empty_output_is_a_failure_not_a_pass(self):
        self.executor.run.return_value = _command_result(
            exit_code=1, stdout="", stderr="Chrome crashed"
        )
        outcome = self.scanner.execute("example.com")
        self.assertEqual(outcome.result.score, 0)
        self.assertEqual(outcome.findings[0].check_code, "lighthouse.no_output")

    def test_invalid_json_is_reported_as_parse_error(self):
        self.executor.run.return_value = _command_result(stdout="<html>oops</html>")
        outcome = self.scanner.execute("example.com")
        self.assertEqual(outcome.result.score, 0)
        self.assertEqual(outcome.findings[0].check_code, "lighthouse.parse_error")

    def test_runtime_error_is_high_severity(self):
        payload = dict(LIGHTHOUSE_REPORT)
        payload["runtimeError"] = {
            "code": "NO_FCP",
            "message": "The page did not paint any content.",
        }
        self.executor.run.return_value = _command_result(stdout=json.dumps(payload))
        outcome = self.scanner.execute("example.com")

        self.assertEqual(outcome.result.score, 0)
        self.assertEqual(outcome.findings[0].check_code, "lighthouse.runtime_error")
        self.assertEqual(outcome.findings[0].severity, Severity.HIGH)

    def test_sandbox_error_is_reported_not_raised(self):
        from scanners.executors.sandbox import SandboxUnavailableError

        self.executor.run.side_effect = SandboxUnavailableError("no slot")
        outcome = self.scanner.execute("example.com")
        self.assertEqual(outcome.result.score, 0)
        self.assertEqual(
            outcome.findings[0].check_code, "lighthouse.sandbox_unavailable"
        )

    # ── Security paths ──

    def test_ssrf_rejection_never_invokes_lighthouse(self):
        with patch(
            "scanners.implementations.lighthouse.validate_target",
            side_effect=TargetValidationError("Target resolves to a private address"),
        ):
            outcome = self.scanner.execute("internal.example.com")

        self.executor.run.assert_not_called()
        self.assertEqual(outcome.result.status, "critical")
        self.assertIsNone(outcome.result.score)
        self.assertEqual(outcome.findings[0].check_code, "lighthouse.target_validation")

    def test_redirect_to_private_address_is_rejected(self):
        payload = dict(LIGHTHOUSE_REPORT)
        payload["finalUrl"] = "http://169.254.169.254/latest/meta-data/"
        self.executor.run.return_value = _command_result(stdout=json.dumps(payload))

        with patch(
            "scanners.implementations.lighthouse.validate_target",
            side_effect=[
                _target(),
                TargetValidationError("Metadata endpoints are not allowed."),
            ],
        ):
            outcome = self.scanner.execute("example.com")

        self.assertEqual(outcome.result.status, "critical")
        self.assertIn("prohibited URL", outcome.result.message)
        self.assertEqual(outcome.findings[0].check_code, "lighthouse.target_validation")

    def test_unavailable_binary_returns_neutral_result(self):
        with patch(
            "scanners.implementations.lighthouse.shutil.which",
            return_value=None,
        ):
            outcome = self.scanner.execute("example.com")

        self.executor.run.assert_not_called()
        self.assertIsNone(outcome.result.score)
        self.assertEqual(outcome.result.status, "neutral")
        self.assertEqual(outcome.findings[0].check_code, "lighthouse.unavailable")


# ═══════════════════════════════════════════════════
# Settings integration
# ═══════════════════════════════════════════════════


@override_settings(
    SCANNER_CONFIG={
        "lighthouse": {
            "timeout": 90,
            "categories": ["performance", "seo"],
            "max_findings": 2,
        }
    }
)
class LighthouseSettingsTests(SimpleTestCase):
    def test_max_findings_caps_audit_findings(self):
        scanner = LighthouseScanner()
        report = parse_lighthouse_json(json.dumps(LIGHTHOUSE_REPORT))
        findings = scanner.normalize(report)
        # 2 category scores + at most 2 audit findings.
        self.assertEqual(len(findings), 4)

    def test_categories_can_be_restricted(self):
        with override_settings(
            SCANNER_CONFIG={"lighthouse": {"categories": ["performance"]}}
        ):
            scanner = LighthouseScanner()
            self.assertEqual(scanner.categories, ("performance",))
