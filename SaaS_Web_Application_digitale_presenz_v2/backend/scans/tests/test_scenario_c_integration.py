"""Stage-2 scenario-C integration tests.

These tests exercise the preparation of the progressive journey pipeline:

* the ``scenario_c`` Nuclei profile emits one ``-t`` per template directory;
* standard/thorough/deep profiles are unchanged (one ``-t``);
* Gobuster's optional complementary pass is merged and de-duplicated;
* journey stage 2 selects its own steps and 360 s budget;
* stage-2 persistence folds a Gobuster path into the content finding that
  already proved the same resource.
"""

from __future__ import annotations

import os
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from accounts.models import User
from scanners.base import FindingStatus, NormalizedFinding, Severity
from scanners.executors.sandbox import (
    SandboxedCommandExecutor,
    SandboxLimits,
)
from scanners.implementations import gobuster as gobuster_module
from scanners.implementations.gobuster import GobusterScanner, _merge_gobuster_paths
from scanners.implementations.nuclei import NucleiScanner
from scanners.implementations.tool_run import ToolRun
from scans.models import Finding, Scan, ScanJourney, ScannerRun
from scans.services.finding_dedup import (
    finding_dedup_key,
    merge_complementary_evidence,
)
from scans.services.orchestrator import (
    ScanOrchestrator,
    _budget_settings_for_scan,
)
from scans.services.steps_builder import build_initial_steps, get_steps_for_scan
from websites.models import Website


class ScenarioCNucleiProfileTests(SimpleTestCase):
    def test_scenario_c_emits_one_template_flag_per_selected_path(self):
        command = NucleiScanner().build_command(
            "https://example.com", profile_name="scenario_c"
        )
        positions = [i for i, value in enumerate(command) if value == "-t"]
        self.assertEqual(len(positions), 2)
        self.assertEqual(
            [command[i + 1] for i in positions],
            [
                "/opt/scanner-templates/selected",
                "/opt/scanner-templates/presence",
            ],
        )
        self.assertIn("-duc", command)
        self.assertEqual(
            command[command.index("-severity") + 1],
            "info,low,medium,high,critical",
        )
        self.assertIn("dos", command[command.index("-exclude-tags") + 1])

    def test_scenario_c_profile_owns_the_180_second_budget(self):
        scanner = NucleiScanner()
        self.assertEqual(scanner.timeout_for_profile("scenario_c"), 180)
        self.assertEqual(scanner.timeout_for_profile("standard"), 150)

    def test_existing_profiles_keep_a_single_template_path(self):
        scanner = NucleiScanner()
        for profile in ("standard", "thorough", "deep"):
            with self.subTest(profile=profile):
                command = scanner.build_command(
                    "https://example.com",
                    templates_path="/nuclei-templates",
                    profile_name=profile,
                )
                self.assertEqual(command.count("-t"), 1)
                self.assertIn("/nuclei-templates", command)

    def test_scenario_c_keeps_each_missing_header_distinct(self):
        """Nuclei emits one JSONL record per header matcher.

        Stage 2 must keep all ten findings; classic profiles keep the
        historical single-finding aggregation (one template id + URL).
        """
        headers = [
            "strict-transport-security",
            "content-security-policy",
            "x-content-type-options",
            "x-permitted-cross-domain-policies",
            "cross-origin-opener-policy",
            "cross-origin-resource-policy",
            "permissions-policy",
            "x-frame-options",
            "referrer-policy",
            "cross-origin-embedder-policy",
        ]
        parsed = [
            {
                "template_id": "http-missing-security-headers",
                "matched_at": "https://example.com/",
                "matcher_name": header,
                "severity": "info",
            }
            for header in headers
        ]
        scanner = NucleiScanner()
        stage_two = scanner.normalize(parsed, preserve_matchers=True)
        self.assertEqual(len(stage_two), 10)
        self.assertEqual(
            sorted(f.check_code for f in stage_two),
            sorted(
                f"nuclei.http-missing-security-headers.{header}" for header in headers
            ),
        )
        # Retro-compatibility: the standard/thorough/deep paths still collapse
        # the ten records exactly as they did before Lot C2.
        self.assertEqual(len(scanner.normalize(parsed)), 1)


class JourneyStepsTests(SimpleTestCase):
    def test_stage_two_selects_scenario_c_without_nikto(self):
        steps = build_initial_steps("security", journey_stage=2)
        self.assertEqual([step["key"] for step in steps], ["nuclei", "gobuster"])
        self.assertEqual(steps[0]["profile"], "scenario_c")
        self.assertNotIn("nikto", {step["scanner"] for step in steps})
        self.assertEqual(
            steps[0]["timeout_setting"], "SCAN_JOURNEY_STAGE2_NUCLEI_TIMEOUT"
        )
        self.assertEqual(
            steps[1]["timeout_setting"], "SCAN_JOURNEY_STAGE2_GOBUSTER_TIMEOUT"
        )

    def test_classic_security_pipeline_is_unchanged(self):
        steps = build_initial_steps("security")
        self.assertEqual(
            [step["key"] for step in steps],
            [
                "nmap",
                "nikto",
                "nuclei",
                "whatweb",
                "testssl",
                "dnsrecon",
                "gobuster",
                "zap",
            ],
        )
        self.assertNotIn("profile", steps[2])

    def test_get_steps_for_scan_distinguishes_journey_and_classic(self):
        journey = SimpleNamespace(scan_type="full", journey_stage=2)
        classic = SimpleNamespace(scan_type="full", journey_stage=None)
        self.assertEqual(
            [step["key"] for step in get_steps_for_scan(journey)],
            ["nuclei", "gobuster"],
        )
        self.assertIn("nikto", [step["key"] for step in get_steps_for_scan(classic)])

    def test_budget_is_360_for_stage_two_and_540_otherwise(self):
        self.assertEqual(
            _budget_settings_for_scan(SimpleNamespace(journey_stage=2)),
            ("SCAN_JOURNEY_STAGE2_TIME_BUDGET_SECONDS", 360),
        )
        self.assertEqual(
            _budget_settings_for_scan(SimpleNamespace(journey_stage=None)),
            ("SCAN_TOTAL_TIME_BUDGET_SECONDS", 540),
        )


class EffectiveTimeoutTests(SimpleTestCase):
    def test_stage_two_step_timeout_overrides_adapter_default(self):
        orchestrator = ScanOrchestrator(1)
        orchestrator._deadline = time.monotonic() + 500
        scanner = SimpleNamespace(timeout=45, profile_timeout=150)
        with override_settings(
            SCAN_JOURNEY_STAGE2_GOBUSTER_TIMEOUT=120,
            SCANNER_SANDBOX={"max_timeout": 300},
        ):
            self.assertEqual(
                orchestrator._effective_timeout(
                    scanner,
                    "gobuster",
                    step={"timeout_setting": "SCAN_JOURNEY_STAGE2_GOBUSTER_TIMEOUT"},
                ),
                120,
            )

    def test_without_step_setting_the_legacy_timeout_is_used(self):
        orchestrator = ScanOrchestrator(1)
        orchestrator._deadline = time.monotonic() + 500
        scanner = SimpleNamespace(timeout=45)
        with override_settings(SCANNER_SANDBOX={"max_timeout": 300}):
            self.assertEqual(orchestrator._effective_timeout(scanner, "gobuster"), 45)


class GobusterExtraPassTests(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.NamedTemporaryFile("w", delete=False)
        self.temp.write("/backup.zip\n/.git/config\n")
        self.temp.close()
        self.addCleanup(lambda: os.unlink(self.temp.name))

    def _settings(self):
        return override_settings(
            SCANNER_CONFIG={
                **settings.SCANNER_CONFIG,
                "gobuster": {
                    **settings.SCANNER_CONFIG["gobuster"],
                    "extra_wordlist": self.temp.name,
                },
            },
            SCANNER_SANDBOX={
                **settings.SCANNER_SANDBOX,
                "mode": "process",
            },
        )

    def test_merge_deduplicates_by_canonical_path(self):
        merged = _merge_gobuster_paths(
            [{"path": "/admin", "status_code": 200}],
            [
                {"path": "/admin", "status_code": 200},
                {"path": "/backup.zip", "status_code": 200},
            ],
        )
        self.assertEqual([item["path"] for item in merged], ["/admin", "/backup.zip"])

    def test_second_pass_runs_and_results_are_merged(self):
        first = ToolRun(
            stdout="/admin (Status: 200) [Size: 10]\n"
            "/backup.zip (Status: 200) [Size: 20]\n",
            exit_code=0,
            duration_ms=10,
        )
        second = ToolRun(
            stdout="/backup.zip (Status: 200) [Size: 20]\n"
            "/.git/config (Status: 200) [Size: 30]\n",
            exit_code=0,
            duration_ms=20,
        )
        commands = []
        timeouts = []

        def runner(_scanner, command, **kwargs):
            commands.append(list(command))
            timeouts.append(kwargs.get("timeout"))
            return first if len(commands) == 1 else second

        with (
            self._settings(),
            patch.object(GobusterScanner, "is_available", return_value=True),
            patch.object(gobuster_module, "run_tool", side_effect=runner),
            patch.object(
                gobuster_module,
                "probe_soft_404",
                return_value=gobuster_module.Soft404Probe(
                    sampled_path="/.presence-soft404-test", status_code=404
                ),
            ),
        ):
            outcome = GobusterScanner().execute("example.com")

        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[1][commands[1].index("-w") + 1], self.temp.name)
        # The second pass receives the remainder of the step budget, never a
        # fresh full timeout on top of the first pass.
        self.assertIsNone(timeouts[0])
        self.assertIsNotNone(timeouts[1])
        self.assertGreaterEqual(timeouts[1], 1)
        self.assertLessEqual(timeouts[1], 45)
        self.assertEqual(outcome.result.details["paths_found"], 3)
        self.assertEqual(len(outcome.result.details["passes"]), 2)
        self.assertEqual(len(outcome.findings), 3)
        self.assertEqual(outcome.result.duration_ms, 30)
        self.assertTrue(outcome.result.details["scan_complete"])

    def test_without_extra_wordlist_the_single_pass_is_unchanged(self):
        commands = []

        def runner(_scanner, command, **_kwargs):
            commands.append(list(command))
            return ToolRun(
                stdout="/admin (Status: 200) [Size: 10]\n",
                exit_code=0,
                duration_ms=5,
            )

        with (
            override_settings(
                SCANNER_CONFIG={
                    **settings.SCANNER_CONFIG,
                    "gobuster": {
                        **settings.SCANNER_CONFIG["gobuster"],
                        "extra_wordlist": "",
                    },
                }
            ),
            patch.object(GobusterScanner, "is_available", return_value=True),
            patch.object(gobuster_module, "run_tool", side_effect=runner),
            patch.object(
                gobuster_module,
                "probe_soft_404",
                return_value=gobuster_module.Soft404Probe(
                    sampled_path="/.presence-soft404-test", status_code=404
                ),
            ),
        ):
            outcome = GobusterScanner().execute("example.com")

        self.assertEqual(len(commands), 1)
        self.assertEqual(len(outcome.findings), 1)
        self.assertTrue(outcome.result.details["scan_complete"])


class SandboxMountTests(SimpleTestCase):
    def test_scenario_templates_are_mounted_read_only(self):
        with tempfile.TemporaryDirectory() as scenario_root:
            config = {
                **settings.SCANNER_CONFIG,
                "nuclei": {
                    **settings.SCANNER_CONFIG["nuclei"],
                    "scenario_templates_path": scenario_root,
                },
            }
            with override_settings(SCANNER_CONFIG=config):
                executor = SandboxedCommandExecutor(mode="docker")
                command = executor.build_docker_command(
                    ["nuclei", "-version"],
                    SandboxLimits(timeout_s=5, cpu_seconds=10),
                    scanner_name="nuclei",
                    docker_image="nuclei:test",
                    mounts=[(scenario_root, "/opt/scanner-templates")],
                )

        mount = command[command.index("--mount") + 1]
        self.assertTrue(mount.endswith(",readonly"), mount)


class FindingDedupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "stage2@example.com", "CorrectHorseBattery1!"
        )
        self.website = Website.objects.create(owner=self.user, domain="example.com")

    def _scan(self, journey_stage=None):
        journey = None
        if journey_stage is not None:
            # The Lot A schema requires a journey to own a non-null stage.
            journey = ScanJourney.objects.create(
                website=self.website,
                requested_by=self.user,
                current_stage=journey_stage,
                total_stages=2,
            )
        return Scan.objects.create(
            website=self.website,
            status=Scan.Status.QUEUED,
            scan_type=Scan.ScanType.SECURITY,
            journey=journey,
            journey_stage=journey_stage,
        )

    @staticmethod
    def _finding(check_code, url, *, category="security"):
        return NormalizedFinding(
            check_code=check_code,
            category=category,
            severity=Severity.HIGH,
            status=FindingStatus.FAIL,
            title=check_code,
            evidence={"matched_at": url},
        )

    def _persist(self, scan, findings, scanner):
        run = ScannerRun.objects.create(scan=scan, scanner=scanner)
        orchestrator = ScanOrchestrator(scan.id)
        orchestrator._dedup_findings = scan.journey_stage == 2
        orchestrator._finding_keys.clear()
        orchestrator._findings_by_path.clear()
        orchestrator._persist_findings(run, findings)
        return orchestrator

    def test_canonical_key_normalizes_case_and_trailing_slash(self):
        self.assertEqual(
            finding_dedup_key("Security", "NUCLEI.GIT", "https://example.com/.git/"),
            ("security", "nuclei.git", "https://example.com/.git"),
        )

    def test_gobuster_path_is_folded_into_content_finding(self):
        scan = self._scan(journey_stage=2)
        nuclei = self._finding("nuclei.git-config", "https://example.com/.git/config")
        gobuster = NormalizedFinding(
            check_code="gobuster.path.git-config",
            category="security",
            severity=Severity.LOW,
            status=FindingStatus.WARNING,
            title="Directory/file found: /.git/config",
            evidence={"path": "/.git/config", "status_code": 200, "size": 12},
        )
        orchestrator = ScanOrchestrator(scan.id)
        orchestrator._dedup_findings = True
        orchestrator._finding_keys.clear()
        orchestrator._findings_by_path.clear()
        run_nuclei = ScannerRun.objects.create(scan=scan, scanner="nuclei")
        run_gobuster = ScannerRun.objects.create(scan=scan, scanner="gobuster")
        orchestrator._persist_findings(run_nuclei, [nuclei])
        orchestrator._persist_findings(run_gobuster, [gobuster])

        stored = Finding.objects.filter(scanner_run__scan=scan)
        self.assertEqual(stored.count(), 1)
        finding = stored.get()
        self.assertEqual(finding.check_code, "nuclei.git-config")
        self.assertEqual(
            finding.evidence["complementary_evidence"][0]["path"], "/.git/config"
        )

    def test_classic_scan_still_persists_both_sources(self):
        scan = self._scan(journey_stage=None)
        nuclei = self._finding("nuclei.git-config", "https://example.com/.git/config")
        gobuster = NormalizedFinding(
            check_code="gobuster.path.git-config",
            category="security",
            severity=Severity.LOW,
            status=FindingStatus.WARNING,
            title="Directory/file found: /.git/config",
            evidence={"path": "/.git/config", "status_code": 200},
        )
        orchestrator = ScanOrchestrator(scan.id)
        run_nuclei = ScannerRun.objects.create(scan=scan, scanner="nuclei")
        run_gobuster = ScannerRun.objects.create(scan=scan, scanner="gobuster")
        orchestrator._persist_findings(run_nuclei, [nuclei])
        orchestrator._persist_findings(run_gobuster, [gobuster])
        self.assertEqual(Finding.objects.filter(scanner_run__scan=scan).count(), 2)

    def test_distinct_header_checks_are_not_collapsed(self):
        scan = self._scan(journey_stage=2)
        findings = [
            self._finding(
                "nuclei.http-missing-security-headers.csp",
                "https://example.com/",
            ),
            self._finding(
                "nuclei.http-missing-security-headers.x-content-type-options",
                "https://example.com/",
            ),
        ]
        self._persist(scan, findings, "nuclei")
        self.assertEqual(Finding.objects.filter(scanner_run__scan=scan).count(), 2)

    def test_duplicate_keeps_highest_severity(self):
        scan = self._scan(journey_stage=2)
        low = self._finding("nuclei.git-config", "https://example.com/.git/config")
        low.severity = Severity.LOW
        high = self._finding("nuclei.git-config", "https://example.com/.git/config")
        high.severity = Severity.HIGH
        self._persist(scan, [low, high], "nuclei")

        stored = Finding.objects.get(scanner_run__scan=scan)
        self.assertEqual(stored.severity, Severity.HIGH)

    def test_robots_file_and_disclosed_paths_remain_distinct(self):
        scan = self._scan(journey_stage=2)
        findings = [
            self._finding("nuclei.robots-txt", "https://example.com/robots.txt"),
            self._finding(
                "nuclei.presence-robots-sensitive-paths",
                "https://example.com/robots.txt",
            ),
        ]
        self._persist(scan, findings, "nuclei")
        self.assertEqual(Finding.objects.filter(scanner_run__scan=scan).count(), 2)

    def test_merge_keeps_structured_evidence_without_secrets(self):
        target = self._finding("nuclei.git-config", "https://example.com/.git/config")
        source = NormalizedFinding(
            check_code="gobuster.path.git-config",
            category="security",
            severity=Severity.LOW,
            status=FindingStatus.WARNING,
            title="found",
            evidence={"path": "/.git/config", "status_code": 200, "size": 12},
        )
        merge_complementary_evidence(target, source)
        self.assertEqual(
            target.evidence["complementary_evidence"][0]["status_code"], 200
        )
        self.assertNotIn("body", target.evidence)
