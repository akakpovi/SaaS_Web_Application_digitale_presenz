"""Advanced security tier tests (ZAP + Nuclei).

External tools are never executed: the sandbox executor and the ZAP REST
session are mocked.  The tests cover the feature gate, single execution,
sandbox limits, command construction, parsing and normalisation.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from scanners.base import FindingStatus, ScanContext, Severity
from scanners.exceptions import TargetValidationError
from scanners.executors.command import CommandResult
from scanners.executors.sandbox import (
    SandboxError,
    SandboxLimits,
    SandboxMode,
    SandboxedCommandExecutor,
)
from scanners.features import advanced_security_enabled
from scanners.implementations.nuclei import NucleiScanner
from scanners.implementations.zap import ZAPScanner
from scanners.parsers.zap import parse_zap_json
from scanners.security.target_validator import TargetInfo


SANDBOX_SETTINGS = {
    "mode": "process",
    "default_timeout": 60,
    "max_timeout": 300,
    "default_memory_mb": 256,
    "default_file_size_mb": 16,
    "default_open_files": 128,
    "max_output_bytes": 64_000,
    "max_concurrency": 0,
    "docker": {
        "binary": "docker",
        "network": "presence_scanner_sandbox",
        "cpus": 1.0,
        "pids_limit": 128,
        "shm_size_mb": 128,
        "pull_policy": "never",
        "start_grace_seconds": 5,
        "images": {"zap": "ghcr.io/zaproxy/zap-stable"},
    },
}

SCANNER_CONFIG = {
    "nuclei": {
        "timeout": 90,
        "tags": ["cve", "exposure"],
        "sandbox": {"memory_mb": 256, "cpu_seconds": 100},
    },
    "zap": {
        "timeout": 120,
        "mode": "docker",
        "docker_image": "ghcr.io/zaproxy/zap-stable",
        "api_url": "http://zap-scanner:8090",
        "active_scan": False,
        "sandbox": {
            "memory_mb": 1024,
            "cpu_seconds": 180,
            "tmpfs": ["/zap/wrk:rw,nosuid,nodev,size=64m"],
        },
    },
}


NUCLEI_STATS = json.dumps(
    {
        "duration": "0:00:01",
        "errors": "0",
        "hosts": "1",
        "matched": "2",
        "percent": "100",
        "requests": "20",
        "rps": "20",
        "startedAt": "2026-10-25T00:00:00Z",
        "templates": "2",
        "total": "2",
    }
)

NUCLEI_JSONL = "\n".join(
    [
        json.dumps(
            {
                "template-id": "CVE-2024-1234",
                "info": {
                    "name": "Example RCE",
                    "severity": "high",
                    "description": "Remote code execution",
                    "tags": ["cve", "rce"],
                    "reference": ["https://nvd.nist.gov/vuln/detail/CVE-2024-1234"],
                },
                "matched-at": "https://example.com/vulnerable",
                "matcher-name": "body",
                "host": "example.com",
            }
        ),
        json.dumps(
            {
                "template-id": "exposed-panel",
                "info": {
                    "name": "Exposed admin panel",
                    "severity": "medium",
                    "description": "Admin panel is public",
                    "tags": ["exposure"],
                },
                "matched-at": "https://example.com/admin",
                "host": "example.com",
            }
        ),
    ]
)


ZAP_REPORT = {
    "site": [
        {
            "@name": "https://example.com",
            "alerts": [
                {
                    "pluginid": "10038",
                    "name": "Content Security Policy (CSP) Header Not Set",
                    "riskdesc": "Medium (High)",
                    "riskcode": "2",
                    "confidence": "High",
                    "desc": "CSP is missing.",
                    "solution": "Set a CSP header.",
                    "reference": "https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP",
                    "cweid": "693",
                    "wascid": "15",
                    "instances": [{"uri": "https://example.com/"}],
                },
                {
                    "pluginid": "90001",
                    "name": "Remote code execution",
                    "riskdesc": "High (High)",
                    "riskcode": "3",
                    "confidence": "High",
                    "desc": "RCE detected.",
                    "solution": "Patch the server.",
                    "reference": "",
                    "cweid": "78",
                    "wascid": "20",
                    "instances": [{"uri": "https://example.com/x"}],
                },
            ],
        }
    ]
}


def _target(hostname: str = "example.com") -> TargetInfo:
    return TargetInfo(
        hostname=hostname,
        url=f"https://{hostname}",
        safe_ips=["93.184.216.34"],
        scheme="https",
    )


def _limits(timeout_s: int = 60) -> SandboxLimits:
    return SandboxLimits(
        timeout_s=timeout_s,
        cpu_seconds=timeout_s + 5,
        memory_mb=256,
        file_size_mb=16,
        open_files=128,
    )


def _context(hostname: str = "example.com", timeout: int = 60) -> ScanContext:
    return ScanContext(
        scan_id=1,
        domain=hostname,
        timeout=timeout,
        deadline_monotonic=time.monotonic() + timeout,
        target=_target(hostname),
        sandbox_limits=_limits(timeout),
    )


class NucleiProfilePolicyTests(SimpleTestCase):
    """The automatic profile must have a real margin under the 180 s goal."""

    def test_standard_profile_is_bounded_and_high_signal(self):
        cfg = settings.SCANNER_CONFIG["nuclei"]
        standard = cfg["profiles"]["standard"]

        self.assertEqual(cfg["profile"], "standard")
        self.assertEqual(standard["severity"], "critical,high")
        self.assertEqual(standard["timeout"], 150)
        self.assertLess(standard["timeout"], 180)
        self.assertFalse(standard["resolve_missing"])
        self.assertIn("dos", standard["exclude_tags"])
        self.assertNotIn("medium", standard["severity"])

    def test_thorough_profile_preserves_medium_coverage(self):
        cfg = settings.SCANNER_CONFIG["nuclei"]
        thorough = cfg["profiles"]["thorough"]

        self.assertEqual(thorough["severity"], "critical,high,medium")
        self.assertEqual(thorough["timeout"], 178)
        self.assertLess(thorough["timeout"], 180)
        self.assertFalse(thorough["resolve_missing"])
        # Explicit opt-in only: the default must stay the fast profile.
        self.assertNotEqual(cfg["profile"], "thorough")

    def test_profile_budgets_fit_the_sandbox_and_celery(self):
        cfg = settings.SCANNER_CONFIG["nuclei"]
        sandbox_max = settings.SCANNER_SANDBOX["max_timeout"]

        for name in ("standard", "thorough"):
            with self.subTest(profile=name):
                self.assertLessEqual(
                    cfg["profiles"][name]["timeout"], sandbox_max
                )
                self.assertLess(
                    cfg["profiles"][name]["timeout"],
                    settings.CELERY_TASK_TIME_LIMIT,
                )
        self.assertLessEqual(
            settings.SCAN_TOTAL_TIME_BUDGET_SECONDS,
            settings.CELERY_TASK_TIME_LIMIT,
        )

    def test_scanner_uses_profile_budget_not_legacy_top_level(self):
        scanner = NucleiScanner()
        self.assertEqual(scanner.profile_timeout, 150)
        self.assertEqual(scanner.timeout, 150)


class FeatureFlagTests(SimpleTestCase):
    @override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=False)
    def test_flag_is_off_by_default_in_this_configuration(self):
        self.assertFalse(advanced_security_enabled())

    @override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=True)
    def test_flag_can_be_enabled_explicitly(self):
        self.assertTrue(advanced_security_enabled())

    @override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=False)
    def test_nuclei_refuses_to_execute_when_disabled(self):
        scanner = NucleiScanner()
        executor = MagicMock()
        with patch(
            "scanners.implementations.nuclei.get_sandbox_executor",
            return_value=executor,
        ):
            outcome = scanner.execute("example.com")

        executor.run.assert_not_called()
        self.assertEqual(outcome.result.status, "neutral")
        self.assertEqual(outcome.findings[0].check_code, "nuclei.disabled")
        self.assertEqual(
            outcome.findings[0].status, FindingStatus.NOT_APPLICABLE
        )
        self.assertFalse(scanner.is_available())

    @override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=False)
    def test_zap_refuses_to_execute_when_disabled(self):
        scanner = ZAPScanner()
        with patch(
            "scanners.implementations.zap.http_requests.Session"
        ) as mock_session, patch(
            "scanners.implementations.zap.get_sandbox_executor"
        ) as mock_executor:
            outcome = scanner.execute("example.com")

        mock_session.assert_not_called()
        mock_executor.return_value.run.assert_not_called()
        self.assertEqual(outcome.findings[0].check_code, "zap.disabled")
        self.assertFalse(scanner.is_available())


@override_settings(
    SCANNER_ADVANCED_SECURITY_ENABLED=True,
    SCANNER_SANDBOX=SANDBOX_SETTINGS,
    SCANNER_CONFIG=SCANNER_CONFIG,
)
class NucleiExecutionTests(SimpleTestCase):
    def setUp(self):
        self.scanner = NucleiScanner()
        self.executor = MagicMock()
        self.executor.mode = SandboxMode.PROCESS
        self.executor.is_available.return_value = True
        self.executor.limits_for.return_value = _limits()
        self.executor.run.return_value = CommandResult(
            exit_code=0,
            stdout=NUCLEI_JSONL,
            stderr=NUCLEI_STATS,
            duration_ms=1234,
        )

        self.patches = [
            patch(
                "scanners.implementations.nuclei.get_sandbox_executor",
                return_value=self.executor,
            ),
            patch(
                "scanners.implementations.nuclei.shutil.which",
                return_value="/usr/local/bin/nuclei",
            ),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_standard_command_is_explicitly_high_critical_only(self):
        config = {
            "nuclei": {
                "profile": "standard",
                # Legacy value is deliberately larger: the profile wins.
                "timeout": 170,
                "profiles": {
                    "standard": {
                        "tags": ["exposure", "misconfig"],
                        "severity": "critical,high",
                        "timeout": 150,
                        "duration_alert_s": 150,
                    }
                },
                "sandbox": {"memory_mb": 1536},
            }
        }
        with override_settings(SCANNER_CONFIG=config):
            scanner = NucleiScanner()
            self.assertEqual(scanner.profile_timeout, 150)
            self.assertEqual(scanner.duration_alert_s, 150)
            command = scanner.build_command("https://example.com")

        self.assertIn("-severity", command)
        severity = command[command.index("-severity") + 1]
        self.assertEqual(severity, "critical,high")
        self.assertNotIn("medium", severity)

    def test_thorough_command_keeps_medium_with_178s_budget(self):
        config = {
            "nuclei": {
                "profile": "thorough",
                "timeout": 170,
                "profiles": {
                    "thorough": {
                        "tags": ["exposure", "misconfig"],
                        "severity": "critical,high,medium",
                        "timeout": 178,
                        "duration_alert_s": 150,
                    }
                },
                "sandbox": {"memory_mb": 1536},
            }
        }
        with override_settings(SCANNER_CONFIG=config):
            scanner = NucleiScanner()
            self.assertEqual(scanner.profile_timeout, 178)
            command = scanner.build_command("https://example.com")

        severity = command[command.index("-severity") + 1]
        self.assertEqual(severity, "critical,high,medium")

    def test_execute_runs_nuclei_once_with_jsonl(self):
        outcome = self.scanner.execute("example.com", context=_context())

        self.assertEqual(self.executor.run.call_count, 1)
        command = self.executor.run.call_args.kwargs["command"]
        self.assertIn("-jsonl", command)
        self.assertIn("https://example.com", command)
        self.assertIn("-tags", command)
        self.assertNotIn("-silent", command)
        self.assertIn("-stats-json", command)
        self.assertIn("-max-host-error", command)
        self.assertIn("-ip-version", command)
        self.assertEqual(outcome.result.status, "critical")
        self.assertIn("2 template match", outcome.result.message)
        self.assertTrue(outcome.result.details["scan_complete"])
        self.assertEqual(outcome.result.details["percent"], 100)
        self.assertEqual(outcome.raw_report, NUCLEI_JSONL)
        self.assertEqual(outcome.raw_report_format, "nuclei-jsonl")
        self.assertTrue(outcome.raw_report_meta["scan_complete"])
        self.assertEqual(
            outcome.raw_report_meta["profile"],
            outcome.result.details["profile"],
        )

    def test_findings_are_normalized(self):
        outcome = self.scanner.execute("example.com", context=_context())
        by_code = {finding.check_code: finding for finding in outcome.findings}

        self.assertIn("nuclei.CVE-2024-1234", by_code)
        high = by_code["nuclei.CVE-2024-1234"]
        self.assertEqual(high.severity, Severity.HIGH)
        self.assertEqual(high.status, FindingStatus.FAIL)
        self.assertEqual(high.category, "security")
        self.assertTrue(high.reference_url.startswith("https://nvd.nist.gov"))

        medium = by_code["nuclei.exposed-panel"]
        self.assertEqual(medium.severity, Severity.MEDIUM)
        self.assertEqual(medium.status, FindingStatus.WARNING)

    def test_legacy_entry_points_do_not_run_nuclei_twice(self):
        self.scanner.scan("example.com")
        self.assertEqual(self.executor.run.call_count, 1)

        self.scanner.scan_findings("example.com")
        self.assertEqual(self.executor.run.call_count, 2)

    def test_timeout_is_reported_as_unknown_finding(self):
        self.executor.run.return_value = CommandResult(
            exit_code=-9,
            stdout="",
            stderr="killed",
            duration_ms=60_000,
            timed_out=True,
        )
        outcome = self.scanner.execute("example.com", context=_context())

        self.assertEqual(outcome.result.status, "warning")
        self.assertEqual(outcome.findings[0].check_code, "nuclei.timeout")
        self.assertEqual(outcome.findings[0].status, FindingStatus.UNKNOWN)
        self.assertFalse(outcome.result.details["scan_complete"])
        self.assertEqual(outcome.result.details["duration_alert_s"], 150)
        self.assertFalse(outcome.result.details["duration_over_alert"])

    def test_completed_run_below_alert_threshold_is_not_flagged(self):
        outcome = self.scanner.execute("example.com", context=_context())

        self.assertTrue(outcome.result.details["scan_complete"])
        self.assertFalse(outcome.result.details["duration_over_alert"])

    def test_timeout_keeps_partial_findings_but_marks_scan_incomplete(self):
        self.executor.run.return_value = CommandResult(
            exit_code=-9,
            stdout=NUCLEI_JSONL,
            stderr='{"percent":"42","requests":"10","templates":"1"}',
            duration_ms=170_000,
            timed_out=True,
        )
        outcome = self.scanner.execute("example.com", context=_context())

        codes = [finding.check_code for finding in outcome.findings]
        self.assertEqual(codes[0], "nuclei.timeout")
        self.assertIn("nuclei.CVE-2024-1234", codes)
        self.assertFalse(outcome.result.details["scan_complete"])
        self.assertEqual(outcome.result.details["percent"], 42)
        self.assertTrue(outcome.result.details["duration_over_alert"])
        # The partial JSONL is still available for the private archive.
        self.assertEqual(outcome.raw_report, NUCLEI_JSONL)
        self.assertFalse(outcome.raw_report_meta["scan_complete"])
        self.assertEqual(outcome.raw_report_meta["partial_reason"], "timeout")

    def test_host_skip_is_never_a_complete_scan(self):
        """Nuclei exits 0 after dropping an unresponsive host.

        Treating that as a complete empty scan would resolve every existing
        finding; it must be flagged as partial instead.
        """
        self.executor.run.return_value = CommandResult(
            exit_code=0,
            stdout="",
            stderr=(
                "[INF] Skipped example.com:443 from target list as found "
                "unresponsive permanently: cause=\"port closed or filtered\"\n"
                '{"percent":"1","requests":"23","templates":"1066"}'
            ),
            duration_ms=1200,
        )
        outcome = self.scanner.execute("example.com", context=_context())

        self.assertFalse(outcome.result.details["scan_complete"])
        self.assertEqual(outcome.result.details["partial_reason"], "host_unresponsive")
        self.assertEqual(outcome.findings[0].check_code, "nuclei.host_unresponsive")
        self.assertEqual(outcome.result.status, "warning")

    def test_non_zero_exit_is_partial_even_with_findings(self):
        self.executor.run.return_value = CommandResult(
            exit_code=2,
            stdout=NUCLEI_JSONL,
            stderr='{"percent":"100","requests":"20","templates":"2"}',
            duration_ms=1234,
        )
        outcome = self.scanner.execute("example.com", context=_context())

        self.assertFalse(outcome.result.details["scan_complete"])
        self.assertEqual(outcome.result.details["partial_reason"], "exit_code")
        self.assertEqual(outcome.findings[0].check_code, "nuclei.execution_failed")

    def test_output_truncation_is_partial_and_never_resolves(self):
        self.executor.run.return_value = CommandResult(
            exit_code=0,
            stdout=NUCLEI_JSONL,
            stderr=NUCLEI_STATS,
            duration_ms=1234,
            output_truncated=True,
        )
        outcome = self.scanner.execute("example.com", context=_context())

        self.assertFalse(outcome.result.details["scan_complete"])
        self.assertEqual(
            outcome.result.details["partial_reason"], "output_truncated"
        )
        self.assertEqual(
            outcome.findings[0].check_code, "nuclei.output_truncated"
        )
        self.assertTrue(outcome.raw_report_meta["output_truncated"])

    def test_missing_stats_is_not_treated_as_a_complete_scan(self):
        self.executor.run.return_value = CommandResult(
            exit_code=0,
            stdout=NUCLEI_JSONL,
            stderr="",
            duration_ms=1234,
        )
        outcome = self.scanner.execute("example.com", context=_context())

        self.assertFalse(outcome.result.details["scan_complete"])
        self.assertEqual(outcome.result.details["partial_reason"], "missing_stats")

    def test_sandbox_failure_is_not_treated_as_a_clean_scan(self):
        self.executor.run.side_effect = SandboxError("no slot")
        outcome = self.scanner.execute("example.com", context=_context())

        self.assertEqual(outcome.result.status, "warning")
        self.assertEqual(
            outcome.findings[0].check_code, "nuclei.sandbox_unavailable"
        )
        # Regression: a sandbox failure must never look like a full run.
        self.assertFalse(outcome.result.details["scan_complete"])
        self.assertEqual(
            outcome.result.details["partial_reason"], "sandbox_unavailable"
        )

    def test_unavailable_outcome_is_explicitly_incomplete(self):
        with patch.object(NucleiScanner, "is_available", return_value=False):
            outcome = self.scanner.execute("example.com", context=_context())

        self.assertEqual(outcome.findings[0].check_code, "nuclei.unavailable")
        self.assertFalse(outcome.result.details["scan_complete"])
        self.assertEqual(outcome.result.details["partial_reason"], "unavailable")

    def test_target_validation_failure_is_a_finding(self):
        with patch(
            "scanners.implementations.nuclei.validate_target",
            side_effect=TargetValidationError("private address"),
        ):
            outcome = self.scanner.execute("example.com")

        self.assertEqual(outcome.findings[0].check_code, "nuclei.target_validation")
        self.assertEqual(outcome.result.status, "critical")


@override_settings(
    SCANNER_ADVANCED_SECURITY_ENABLED=True,
    SCANNER_SANDBOX=SANDBOX_SETTINGS,
    SCANNER_CONFIG=SCANNER_CONFIG,
)
class ZAPTests(SimpleTestCase):
    def _docker_executor(self):
        executor = MagicMock()
        executor.mode = SandboxMode.DOCKER
        executor.docker_available.return_value = True
        executor.docker_image_for.return_value = "ghcr.io/zaproxy/zap-stable"
        executor.limits_for.return_value = _limits(120)
        return executor

    def test_docker_transport_uses_sandbox_mounts_and_tmpfs(self):
        executor = self._docker_executor()
        captured: dict = {}

        def fake_run(command, **kwargs):
            captured["command"] = command
            captured["kwargs"] = kwargs
            host_dir = kwargs["mounts"][0][0]
            Path(host_dir, "zap-report.json").write_text(
                json.dumps(ZAP_REPORT), encoding="utf-8"
            )
            return CommandResult(
                exit_code=1, stdout="", stderr="", duration_ms=1500
            )

        executor.run.side_effect = fake_run

        with patch(
            "scanners.implementations.zap.get_sandbox_executor",
            return_value=executor,
        ):
            outcome = ZAPScanner().execute("example.com", context=_context(timeout=120))

        command = captured["command"]
        self.assertEqual(command[0], "zap-baseline.py")
        self.assertEqual(command[1], "-t")
        self.assertEqual(command[2], "https://example.com")
        self.assertEqual(captured["kwargs"]["docker_entrypoint"], "")
        self.assertIn("-J", command)
        self.assertIn("/zap/wrk/zap-report.json", command)
        self.assertIn("-I", command)
        self.assertIn("--autooff", command)

        kwargs = captured["kwargs"]
        self.assertEqual(kwargs["docker_image"], "ghcr.io/zaproxy/zap-stable")
        self.assertEqual(kwargs["scanner_name"], "zap")
        self.assertEqual(kwargs["mounts"][0][1], "/zap/wrk")
        # /zap/wrk is a bind mount; a tmpfs on the same path would make
        # Docker reject the container with a duplicate mount point.
        self.assertEqual(kwargs["docker_tmpfs"], [])

        self.assertEqual(outcome.result.status, "critical")
        self.assertTrue(outcome.result.details["transport"] == "docker")
        by_code = {finding.check_code: finding for finding in outcome.findings}
        self.assertIn("zap.alert.90001", by_code)
        self.assertEqual(by_code["zap.alert.90001"].severity, Severity.HIGH)
        self.assertEqual(by_code["zap.alert.90001"].status, FindingStatus.FAIL)
        self.assertIn("zap.alert.10038", by_code)

    def test_docker_missing_report_is_a_sandbox_error(self):
        executor = self._docker_executor()
        executor.run.return_value = CommandResult(
            exit_code=0, stdout="", stderr="", duration_ms=10
        )

        with patch(
            "scanners.implementations.zap.get_sandbox_executor",
            return_value=executor,
        ):
            outcome = ZAPScanner().execute("example.com", context=_context())

        self.assertEqual(outcome.findings[0].check_code, "zap.sandbox_unavailable")

    def test_api_transport_parses_core_alerts(self):
        config = dict(SCANNER_CONFIG)
        config["zap"] = {**SCANNER_CONFIG["zap"], "mode": "api"}

        session = MagicMock()
        spider = MagicMock(ok=True)
        spider.json.return_value = {"scan": "1"}
        status = MagicMock(ok=True)
        status.json.return_value = {"status": "100"}
        alerts = MagicMock(ok=True)
        alerts.text = json.dumps(
            {
                "alerts": [
                    {
                        "pluginid": "10020",
                        "name": "Missing anti-clickjacking header",
                        "risk": "Medium",
                        "confidence": "Medium",
                        "description": "X-Frame-Options is missing.",
                        "solution": "Set X-Frame-Options.",
                        "reference": "",
                        "cweid": "1021",
                        "wascid": "15",
                    }
                ]
            }
        )
        session.get.side_effect = [spider, status, alerts]

        with override_settings(SCANNER_CONFIG=config), patch(
            "scanners.implementations.zap.ZAPScanner._api_available",
            return_value=True,
        ), patch(
            "scanners.implementations.zap.http_requests.Session",
            return_value=session,
        ):
            outcome = ZAPScanner().execute("example.com", context=_context())

        self.assertEqual(outcome.result.details["transport"], "api")
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.findings[0].check_code, "zap.alert.10020")
        self.assertEqual(outcome.findings[0].severity, Severity.MEDIUM)

    def test_api_active_scan_is_not_run_by_default(self):
        config = dict(SCANNER_CONFIG)
        config["zap"] = {**SCANNER_CONFIG["zap"], "mode": "api"}

        session = MagicMock()
        spider = MagicMock(ok=True)
        spider.json.return_value = {"scan": "1"}
        status = MagicMock(ok=True)
        status.json.return_value = {"status": "100"}
        alerts = MagicMock(ok=True)
        alerts.text = json.dumps({"alerts": []})
        session.get.side_effect = [spider, status, alerts]

        with override_settings(SCANNER_CONFIG=config), patch(
            "scanners.implementations.zap.ZAPScanner._api_available",
            return_value=True,
        ), patch(
            "scanners.implementations.zap.http_requests.Session",
            return_value=session,
        ):
            ZAPScanner().execute("example.com", context=_context())

        called_urls = [call.args[0] for call in session.get.call_args_list]
        self.assertFalse(any("/ascan/" in url for url in called_urls))


class ZAPParserTests(SimpleTestCase):
    def test_parses_baseline_report(self):
        parsed = parse_zap_json(json.dumps(ZAP_REPORT))
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["severity"], "medium")
        self.assertEqual(parsed[1]["severity"], "high")

    def test_parses_core_api_alerts(self):
        parsed = parse_zap_json(
            json.dumps(
                {
                    "alerts": [
                        {
                            "pluginid": "10038",
                            "name": "CSP missing",
                            "risk": "High",
                            "riskcode": "3",
                            "cweid": "693",
                        }
                    ]
                }
            )
        )
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["severity"], "high")
        self.assertEqual(parsed[0]["alert_id"], "10038")

    def test_malformed_and_empty_reports_are_safe(self):
        self.assertEqual(parse_zap_json(""), [])
        self.assertEqual(parse_zap_json("not json"), [])
        self.assertEqual(parse_zap_json("[]"), [])


@override_settings(
    SCANNER_ADVANCED_SECURITY_ENABLED=True,
    SCANNER_SANDBOX=SANDBOX_SETTINGS,
    SCANNER_CONFIG=SCANNER_CONFIG,
)
class SandboxMountTests(SimpleTestCase):
    def test_extra_tmpfs_is_added_to_docker_command(self):
        executor = SandboxedCommandExecutor(mode=SandboxMode.DOCKER)
        argv = executor.build_docker_command(
            ["-t", "https://example.com"],
            _limits(),
            scanner_name="zap",
        )
        self.assertIn("/zap/wrk:rw,nosuid,nodev,size=64m", argv)

    def test_output_directory_under_tmp_is_accepted(self):
        executor = SandboxedCommandExecutor(mode=SandboxMode.DOCKER)
        workdir = tempfile.mkdtemp(prefix="presence-test-")
        self.addCleanup(lambda: os.rmdir(workdir))

        argv = executor.build_docker_command(
            ["-t", "https://example.com"],
            _limits(),
            scanner_name="zap",
            mounts=[(workdir, "/out")],
        )
        joined = " ".join(argv)
        self.assertIn("type=bind", joined)
        self.assertIn(f"src={workdir}", joined)
        self.assertIn("dst=/out", joined)

    def test_entrypoint_can_be_cleared_for_zap(self):
        executor = SandboxedCommandExecutor(mode=SandboxMode.DOCKER)
        argv = executor.build_docker_command(
            ["zap-baseline.py", "-t", "https://example.com"],
            _limits(),
            scanner_name="zap",
            docker_entrypoint="",
        )
        index = argv.index("--entrypoint")
        self.assertEqual(argv[index + 1], "")

    def test_bind_mount_outside_tmp_is_refused(self):
        executor = SandboxedCommandExecutor(mode=SandboxMode.DOCKER)
        with self.assertRaises(SandboxError):
            executor.build_docker_command(
                ["-t", "https://example.com"],
                _limits(),
                scanner_name="zap",
                mounts=[("/etc", "/out")],
            )

    def test_invalid_container_path_is_refused(self):
        executor = SandboxedCommandExecutor(mode=SandboxMode.DOCKER)
        workdir = tempfile.mkdtemp(prefix="presence-test-")
        self.addCleanup(lambda: os.rmdir(workdir))

        with self.assertRaises(SandboxError):
            executor.build_docker_command(
                ["-t", "https://example.com"],
                _limits(),
                scanner_name="zap",
                mounts=[(workdir, "/out/../etc")],
            )


class AdvancedScannerCommandTests(SimpleTestCase):
    """The adapters must only use arguments the sandbox can honour.

    The sandbox root filesystem is read-only, so a tool that can only write its
    report to a *file* needs the mounted work directory; a tool that can write
    to stdout must not be told to write a file.  Both mistakes were observed on
    the real stack (nikto silently produced an empty report), hence the
    explicit command-level assertions.
    """

    def test_nikto_reports_to_stdout_without_a_format_file(self):
        from scanners.implementations.nikto import NiktoScanner

        command = NiktoScanner().build_command("example.com")
        self.assertEqual(command[0], "nikto")
        self.assertNotIn("-Format", command)
        self.assertNotIn("-o", command)
        # Its own budget must stay below the sandbox timeout so the report is
        # closed before the container is killed.
        self.assertIn("-maxtime", command)
        self.assertIn("-nointeractive", command)

    def test_testssl_requests_every_covered_category(self):
        """``--std`` alone is cipher-only; all four other categories must be
        requested explicitly, or the report looks complete while containing no
        protocol, certificate, HSTS or vulnerability result."""
        from scanners.implementations.testssl import TestSSLScanner

        command = TestSSLScanner().build_command(
            "example.com", jsonfile="/tmp/report/testssl.json"
        )
        for flag in (
            "--std",
            "--protocols",
            "--server-defaults",
            "--headers",
            "--vulnerable",
        ):
            with self.subTest(flag=flag):
                self.assertIn(flag, command)
        self.assertEqual(command[command.index("--ip") + 1], "one")
        self.assertIn("/tmp/report/testssl.json", command)
        self.assertIn("--jsonfile-pretty", command)
        self.assertEqual(command[-1], "example.com:443")

    def test_dnsrecon_stays_standard_enumeration_only(self):
        from scanners.implementations.dnsrecon import DnsreconScanner

        command = DnsreconScanner().build_command("example.com")
        self.assertIn("-t", command)
        self.assertEqual(command[command.index("-t") + 1], "std")
        # No zone transfer and no brute force in the default command.
        for forbidden in ("axfr", "brt", "srv", "rvl"):
            self.assertNotIn(forbidden, command)

    def test_gobuster_uses_a_bounded_wordlist_and_threads(self):
        from scanners.implementations.gobuster import GobusterScanner

        command = GobusterScanner().build_command("https://example.com")
        self.assertIn("dir", command)
        self.assertIn("-w", command)
        threads = int(command[command.index("-t") + 1])
        self.assertLessEqual(threads, 20)
