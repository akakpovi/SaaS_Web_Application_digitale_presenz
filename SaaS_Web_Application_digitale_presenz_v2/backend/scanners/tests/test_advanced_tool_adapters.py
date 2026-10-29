"""Advanced scanner adapters: single execution, honest completeness, budgets.

The six external tools (nmap, nikto, whatweb, testssl.sh, dnsrecon, gobuster)
share one sandbox image and one contract:

* the tool runs exactly **once** per scan step (``execute()``);
* the report is parsed from that single run;
* an interrupted, truncated, failed or self-truncated run is reported as
  incomplete (``scan_complete=False`` + machine-readable ``partial_reason``),
  so the orchestrator can never mark the step ``completed`` and no missing
  finding can be treated as "no longer present".

Nothing here needs Docker, the tools, or the network: the sandbox call is
replaced by a recorded fake and the parsers run on fixtures.
"""

from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from scanners.base import FindingStatus
from scanners.implementations import (
    dnsrecon as dnsrecon_module,
    gobuster as gobuster_module,
    nikto as nikto_module,
    nmap as nmap_module,
    testssl as testssl_module,
    whatweb as whatweb_module,
)
from scanners.implementations.dnsrecon import dnsrecon_scanner
from scanners.implementations.gobuster import gobuster_scanner
from scanners.implementations.nikto import nikto_scanner
from scanners.implementations.nmap import nmap_scanner
from scanners.implementations.testssl import testssl_scanner
from scanners.implementations.tool_run import ToolRun
from scanners.implementations.whatweb import whatweb_scanner
from scanners.registry import ScannerRegistry
from scanners.security.target_validator import TargetInfo

ADVANCED_SCANNERS = (
    nmap_scanner,
    nikto_scanner,
    whatweb_scanner,
    testssl_scanner,
    dnsrecon_scanner,
    gobuster_scanner,
)

_ADAPTER_MODULE = {
    "nmap": nmap_module,
    "nikto": nikto_module,
    "whatweb": whatweb_module,
    "testssl": testssl_module,
    "dnsrecon": dnsrecon_module,
    "gobuster": gobuster_module,
}

NMAP_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <address addr="93.184.216.34" addrtype="ipv4"/>
    <status state="up"/>
    <ports>
      <port protocol="tcp" portid="443">
        <state state="open"/>
        <service name="https" product="nginx" version="1.24.0"/>
      </port>
      <port protocol="tcp" portid="3306">
        <state state="open"/>
        <service name="mysql" product="MySQL" version="8.0.36"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""

NIKTO_JSON = (
    '{"host":"example.com","vulnerabilities":['
    '{"id":"999957","osvdb":"0","url":"/admin","method":"GET",'
    '"msg":"/admin: Admin login page found"}]}'
)

WHATWEB_JSON = (
    '{"target":"https://example.com","http_status":200,'
    '"plugins":{"nginx":{"version":["1.24.0"]},"PHP":{"version":["8.2.7"]}}}'
)

TESTSSL_JSON = (
    '{"scanResult":['
    '{"id":"cert_expiration","ip":"93.184.216.34","port":"443",'
    '"severity":"OK","finding":"Certificate expires in 90 days"},'
    '{"id":"TLS1_0","ip":"93.184.216.34","port":"443",'
    '"severity":"HIGH","finding":"TLS 1.0 offered"}]}'
)

# ``testssl --jsonfile-pretty`` groups checks by section instead of emitting a
# flat array.  The same cipher check legitimately appears in ``ciphers`` and
# ``cipherTests`` and must be reported once.
TESTSSL_NESTED_JSON = (
    '{"scanResult":[{"targetHost":"example.com","ip":"93.184.216.34",'
    '"port":"443","pretest":['
    '{"id":"engine_problem","severity":"WARN","finding":"No engine support"}'
    '],"ciphers":['
    '{"id":"cipherlist_AVERAGE","severity":"LOW","finding":"offered"}'
    '],"cipherTests":['
    '{"id":"cipherlist_AVERAGE","severity":"LOW","finding":"offered"}'
    ']}]}'
)

TESTSSL_FULL_COVERAGE_JSON = (
    '{"scanResult":[{"targetHost":"example.com","ip":"93.184.216.34",'
    '"port":"443",'
    '"protocols":[{"id":"TLS1_0","severity":"HIGH",'
    '"finding":"TLS 1.0 offered"}],'
    '"serverDefaults":[{"id":"cert_expirationStatus","severity":"OK",'
    '"finding":"Certificate expires in 90 days"}],'
    '"headerResponse":[{"id":"HSTS_time","severity":"OK",'
    '"finding":"365 days"}],'
    '"vulnerabilities":[{"id":"heartbleed","severity":"OK",'
    '"finding":"not vulnerable"}]}]}'
)

DNSRECON_JSON = (
    '[{"type":"A","name":"example.com","address":"93.184.216.34"},'
    '{"type":"MX","name":"example.com","address":"10 mail.example.com"}]'
)

GOBUSTER_TEXT = (
    "/admin                (Status: 301) [Size: 0]\n"
    "/.git                 (Status: 403) [Size: 281]\n"
)


def _target() -> TargetInfo:
    return TargetInfo(
        hostname="example.com",
        url="https://example.com",
        safe_ips=["93.184.216.34"],
        scheme="https",
    )


def _run(**kwargs) -> ToolRun:
    defaults = dict(exit_code=0, stdout="report", stderr="", duration_ms=1234)
    defaults.update(kwargs)
    return ToolRun(**defaults)


class _Recorder:
    """Counts how many times the sandbox was asked to run a tool."""

    def __init__(self) -> None:
        self.calls = 0


def _fake_executor(run: ToolRun, recorder: _Recorder, error: Exception | None):
    """Executor double for adapters that call the executor directly."""
    from types import SimpleNamespace

    from scanners.executors.sandbox import SandboxLimits, SandboxMode

    class _Executor:
        mode = SandboxMode.PROCESS
        max_output_bytes = 1024 * 1024

        def limits_for(self, scanner_name, *, timeout=None):
            return SandboxLimits(
                timeout_s=int(timeout or 60),
                cpu_seconds=60,
                memory_mb=256,
                pids_limit=0,
                file_size_mb=64,
                open_files=256,
            )

        def run(self, command, **kwargs):
            recorder.calls += 1
            if error is not None:
                raise error
            return SimpleNamespace(
                stdout=run.stdout,
                stderr=run.stderr,
                exit_code=run.exit_code,
                duration_ms=run.duration_ms,
                command=list(command),
                timed_out=run.timed_out,
                output_truncated=run.output_truncated,
                memory_exceeded=run.memory_exceeded,
                killed_reason=run.killed_reason,
            )

    return _Executor()


def _execute(
    scanner,
    run: ToolRun,
    *,
    error: Exception | None = None,
    probe=None,
):
    """Run *scanner* once with the sandbox call replaced by *run*.

    Returns ``(outcome, recorder)`` where ``recorder.calls`` proves how many
    times the tool was actually launched.
    """
    module = _ADAPTER_MODULE[scanner.name]
    recorder = _Recorder()

    if scanner.name == "testssl":
        # testssl.sh collects its JSON report from a bind-mounted directory and
        # calls the executor directly instead of the shared run_tool() helper.
        runner_patch = patch.object(
            module,
            "get_sandbox_executor",
            return_value=_fake_executor(run, recorder, error),
        )
    else:
        def _runner(*args, **kwargs):
            recorder.calls += 1
            if error is not None:
                raise error
            return run

        runner_patch = patch.object(module, "run_tool", _runner)

    if scanner.name == "gobuster":
        probe_patch = patch.object(
            module,
            "probe_soft_404",
            return_value=probe
            or module.Soft404Probe(
                sampled_path="/.presence-soft404-test", status_code=404
            ),
        )
    else:
        from contextlib import nullcontext

        probe_patch = nullcontext()

    with patch.object(
        type(scanner), "is_available", return_value=True
    ), runner_patch, probe_patch:
        outcome = scanner.execute("example.com")
    return outcome, recorder


class AdvancedScannerWiringTests(SimpleTestCase):
    """Every advanced scanner is registered, budgeted and given an image."""

    def test_all_six_are_registered_with_images_and_timeouts(self):
        from django.conf import settings

        images = settings.SCANNER_SANDBOX["docker"]["images"]

        for scanner in ADVANCED_SCANNERS:
            with self.subTest(scanner=scanner.name):
                self.assertTrue(ScannerRegistry.is_registered(scanner.name))
                self.assertTrue(images.get(scanner.name))
                self.assertEqual(images[scanner.name], settings.SCANNER_TOOLS_IMAGE)
                self.assertGreater(scanner.timeout, 0)

    def test_second_timeouts_fit_the_scan_budget(self):
        """The six required steps must be able to finish inside one scan."""
        from django.conf import settings

        total = sum(scanner.timeout for scanner in ADVANCED_SCANNERS)
        self.assertLess(total, settings.SCAN_TOTAL_TIME_BUDGET_SECONDS)
        for scanner in ADVANCED_SCANNERS:
            with self.subTest(scanner=scanner.name):
                self.assertLessEqual(scanner.timeout, 300)

    def test_reports_are_archived_for_every_advanced_scanner(self):
        from django.conf import settings

        archived = set(settings.SCANNER_ARCHIVE_SCANNERS)
        for scanner in ADVANCED_SCANNERS:
            with self.subTest(scanner=scanner.name):
                self.assertIn(scanner.name, archived)

    def test_commands_are_argv_only_and_scoped(self):
        # Tolerated only for what the sandbox can write: nikto reports on
        # stdout (its report *file* cannot be opened on the read-only root
        # filesystem), testssl writes into the mounted work directory.
        cases = {
            "nmap": ("-oX", "-", "nmap"),
            "nikto": ("-h", "-maxtime", "nikto"),
            "whatweb": ("--log-json", "whatweb"),
            "testssl": (
                "--std",
                "--protocols",
                "--server-defaults",
                "--headers",
                "--vulnerable",
                "--jsonfile-pretty",
                "testssl",
            ),
            "dnsrecon": ("-t", "std", "dnsrecon"),
            "gobuster": ("dir", "-w", "gobuster"),
        }
        for name, expected in cases.items():
            scanner = _ADAPTER_MODULE[name]
            instance = getattr(scanner, f"{name}_scanner")
            argv = instance.build_command("example.com")
            with self.subTest(scanner=name):
                self.assertIsInstance(argv, list)
                self.assertTrue(all(isinstance(part, str) for part in argv))
                for token in expected:
                    self.assertIn(token, argv)

    def test_gobuster_wordlist_is_the_image_wordlist(self):
        from django.conf import settings

        wordlist = settings.SCANNER_CONFIG["gobuster"]["wordlist"]
        self.assertEqual(wordlist, "/usr/share/dirb/wordlists/common.txt")
        self.assertIn(wordlist, gobuster_scanner.build_command("https://example.com"))


class AdvancedScannerSingleRunTests(SimpleTestCase):
    """One scan step = exactly one tool execution."""

    def test_each_adapter_executes_the_tool_once(self):
        runs = {
            "nmap": _run(stdout=NMAP_XML, stderr="Nmap done"),
            "nikto": _run(stdout=NIKTO_JSON),
            "whatweb": _run(stdout=WHATWEB_JSON),
            "testssl": _run(stdout=TESTSSL_JSON),
            "dnsrecon": _run(stdout=DNSRECON_JSON),
            "gobuster": _run(stdout=GOBUSTER_TEXT),
        }
        for scanner in ADVANCED_SCANNERS:
            with self.subTest(scanner=scanner.name):
                outcome, runner = _execute(scanner, runs[scanner.name])
                self.assertEqual(runner.calls, 1)
                self.assertTrue(
                    outcome.result.details["scan_complete"],
                    outcome.result.details["partial_reason"],
                )
                self.assertFalse(outcome.result.details["timed_out"])
                self.assertEqual(outcome.result.details["partial_reason"], "")
                self.assertTrue(outcome.result.details["exit_code"] == 0)

    def test_legacy_entry_points_do_not_double_run_inside_one_call(self):
        """scan()/scan_findings() delegate to execute() instead of re-running."""
        recorder = _Recorder()

        def _runner(*args, **kwargs):
            recorder.calls += 1
            return _run(stdout=NMAP_XML, stderr="Nmap done")

        with patch.object(
            type(nmap_scanner), "is_available", return_value=True
        ), patch.object(nmap_module, "run_tool", _runner):
            result = nmap_scanner.scan("example.com")
            self.assertEqual(recorder.calls, 1)
            findings = nmap_scanner.scan_findings("example.com")
            # One more explicit legacy call → one more run, never two.
            self.assertEqual(recorder.calls, 2)

        self.assertEqual(result.details["exit_code"], 0)
        self.assertTrue(findings)


class AdvancedScannerCompletenessTests(SimpleTestCase):
    """Incomplete runs must be reported as incomplete, with a reason."""

    def test_timeout_is_incomplete(self):
        run = _run(timed_out=True, exit_code=-1, killed_reason="timeout")
        for scanner in ADVANCED_SCANNERS:
            with self.subTest(scanner=scanner.name):
                outcome, _ = _execute(scanner, run)
                details = outcome.result.details
                self.assertFalse(details["scan_complete"])
                self.assertEqual(details["partial_reason"], "timeout")
                self.assertTrue(details["timed_out"])
                # The diagnostic finding is what tells an operator why nothing
                # was resolved, and it is never a vulnerability.
                diagnostic = next(
                    f
                    for f in outcome.findings
                    if f.check_code.endswith(".timeout")
                )
                self.assertEqual(diagnostic.status, FindingStatus.UNKNOWN)
                self.assertEqual(diagnostic.severity, "info")

    def test_non_zero_exit_code_is_incomplete(self):
        run = _run(exit_code=1, stdout="partial report")
        for scanner in ADVANCED_SCANNERS:
            with self.subTest(scanner=scanner.name):
                outcome, _ = _execute(scanner, run)
                details = outcome.result.details
                self.assertFalse(details["scan_complete"])
                self.assertEqual(details["partial_reason"], "exit_code_1")

    def test_truncated_report_is_incomplete(self):
        run = _run(
            stdout="{}",
            output_truncated=True,
            max_output_bytes=1024,
        )
        for scanner in ADVANCED_SCANNERS:
            with self.subTest(scanner=scanner.name):
                outcome, _ = _execute(scanner, run)
                details = outcome.result.details
                self.assertFalse(details["scan_complete"])
                self.assertIn("output_truncated", details["partial_reason"])

    def test_memory_kill_is_incomplete(self):
        run = _run(exit_code=137, memory_exceeded=True, killed_reason="memory")
        for scanner in ADVANCED_SCANNERS:
            with self.subTest(scanner=scanner.name):
                outcome, _ = _execute(scanner, run)
                details = outcome.result.details
                self.assertFalse(details["scan_complete"])
                self.assertEqual(details["partial_reason"], "memory_exceeded")

    def test_empty_report_is_incomplete_except_for_quiet_tools(self):
        run = _run(stdout="", stderr="")
        for scanner in ADVANCED_SCANNERS:
            with self.subTest(scanner=scanner.name):
                outcome, _ = _execute(scanner, run)
                details = outcome.result.details
                if scanner.name == "gobuster":
                    # Gobuster is silent when a complete run finds nothing.
                    self.assertTrue(details["scan_complete"])
                elif scanner.name == "testssl":
                    self.assertFalse(details["scan_complete"])
                    self.assertEqual(details["partial_reason"], "empty_report")
                else:
                    self.assertFalse(details["scan_complete"])
                    self.assertEqual(details["partial_reason"], "empty_output")

    def test_malformed_report_is_incomplete(self):
        """Output the parser cannot read is not a coverage proof."""
        run = _run(stdout="<html>not a report</html>")
        for scanner in ADVANCED_SCANNERS:
            if scanner.name == "gobuster":
                # Gobuster output is free-form: unreadable lines are simply
                # ignored, and a complete run that finds nothing is silent.
                continue
            with self.subTest(scanner=scanner.name):
                outcome, _ = _execute(scanner, run)
                details = outcome.result.details
                self.assertFalse(details["scan_complete"])
                self.assertIn(
                    details["partial_reason"],
                    ("unparsable_report", "empty_report"),
                )
                self.assertTrue(
                    any(
                        f.check_code.endswith(
                            (".incomplete", ".unparsable_report")
                        )
                        for f in outcome.findings
                    )
                )

    def test_nmap_host_timeout_is_incomplete_even_with_exit_zero(self):
        run = _run(
            stdout=NMAP_XML,
            stderr="Skipping host 93.184.216.34 due to host timeout",
        )
        outcome, _ = _execute(nmap_scanner, run)
        details = outcome.result.details
        self.assertFalse(details["scan_complete"])
        self.assertEqual(details["partial_reason"], "host_timeout")
        # Partial data is still kept for diagnosis.
        self.assertTrue(outcome.findings)

    def test_nikto_maxtime_is_incomplete_even_with_exit_zero(self):
        run = _run(
            stdout=NIKTO_JSON,
            stderr="+ ERROR: Host maximum execution time of 90 seconds reached",
        )
        outcome, _ = _execute(nikto_scanner, run)
        details = outcome.result.details
        self.assertFalse(details["scan_complete"])
        self.assertEqual(details["partial_reason"], "maxtime_reached")

    def test_unavailable_scanner_never_claims_completeness(self):
        for scanner in ADVANCED_SCANNERS:
            module = _ADAPTER_MODULE[scanner.name]
            # An unavailable scanner must not even reach the sandbox; the
            # testssl adapter resolves availability before calling it.
            guards = [patch.object(type(scanner), "is_available", return_value=False)]
            if scanner.name != "testssl":
                guards.append(patch.object(module, "run_tool"))
            with self.subTest(scanner=scanner.name):
                with guards[0], guards[1] if len(guards) > 1 else nullcontext():
                    outcome = scanner.execute("example.com")
                self.assertFalse(outcome.result.details["scan_complete"])
                self.assertEqual(
                    outcome.result.details["partial_reason"], "unavailable"
                )
                self.assertEqual(
                    outcome.findings[0].status, FindingStatus.NOT_APPLICABLE
                )

    def test_execution_diagnostics_are_never_vulnerabilities(self):
        """Incomplete runs carry only diagnostics: no FAIL/PASS findings."""
        run = _run(timed_out=True, exit_code=-1, killed_reason="timeout")
        for scanner in ADVANCED_SCANNERS:
            with self.subTest(scanner=scanner.name):
                outcome, _ = _execute(scanner, run)
                self.assertTrue(outcome.findings)
                # No pass and no vulnerability can be claimed by a run that
                # never completed...
                self.assertFalse(
                    [
                        f
                        for f in outcome.findings
                        if f.status in (FindingStatus.PASS, FindingStatus.FAIL)
                    ]
                )
                # ...and the reason is stated in the findings themselves.
                self.assertTrue(
                    any(
                        f.check_code.endswith(
                            (
                                ".timeout",
                                ".incomplete",
                                ".unparsable_report",
                                ".empty_report",
                            )
                        )
                        for f in outcome.findings
                    )
                )


class AdvancedScannerFindingTests(SimpleTestCase):
    """Normalisation of real tool output shapes."""

    def test_nmap_ports_are_normalised(self):
        outcome, _ = _execute(
            nmap_scanner, _run(stdout=NMAP_XML, stderr="Nmap done")
        )
        codes = {finding.check_code for finding in outcome.findings}
        self.assertIn("nmap.open_port.443", codes)
        self.assertIn("nmap.open_ports_summary", codes)
        # 443 is an expected web port; 3306 (MySQL) is not.
        port_3306 = next(
            f for f in outcome.findings if f.check_code == "nmap.open_port.3306"
        )
        self.assertEqual(port_3306.severity, "medium")
        self.assertEqual(port_3306.status, FindingStatus.WARNING)
        port_443 = next(
            f for f in outcome.findings if f.check_code == "nmap.open_port.443"
        )
        self.assertEqual(port_443.status, FindingStatus.PASS)

    def test_nikto_json_is_normalised(self):
        outcome, _ = _execute(nikto_scanner, _run(stdout=NIKTO_JSON))
        self.assertTrue(outcome.findings)
        self.assertEqual(outcome.findings[0].status, FindingStatus.FAIL)
        self.assertIn("/admin", outcome.findings[0].description)

    def test_whatweb_technologies_are_normalised(self):
        outcome, _ = _execute(whatweb_scanner, _run(stdout=WHATWEB_JSON))
        codes = {finding.check_code for finding in outcome.findings}
        self.assertIn("whatweb.technology.php", codes)
        self.assertIn("whatweb.technologies_summary", codes)
        php = next(
            f for f in outcome.findings if f.check_code == "whatweb.technology.php"
        )
        self.assertEqual(php.status, FindingStatus.WARNING)

    def test_testssl_severities_are_normalised(self):
        outcome, _ = _execute(
            testssl_scanner, _run(stdout=TESTSSL_JSON, stderr="testssl done")
        )
        high = next(
            f for f in outcome.findings if f.check_code == "testssl.TLS1_0"
        )
        self.assertEqual(high.severity, "high")
        self.assertEqual(high.status, FindingStatus.FAIL)

    def test_testssl_sectioned_report_yields_identified_checks(self):
        """The real pretty-JSON shape nests checks; none may end up nameless."""
        from scanners.parsers.testssl import parse_testssl_json

        parsed = parse_testssl_json(TESTSSL_NESTED_JSON)
        self.assertEqual(
            sorted(item["id"] for item in parsed),
            ["cipherlist_AVERAGE", "engine_problem"],
        )

        outcome, _ = _execute(testssl_scanner, _run(stdout=TESTSSL_NESTED_JSON))
        codes = [finding.check_code for finding in outcome.findings]
        self.assertEqual(
            sorted(codes), ["testssl.cipherlist_AVERAGE", "testssl.engine_problem"]
        )
        self.assertNotIn("testssl.", codes)
        for finding in outcome.findings:
            self.assertTrue(finding.title.strip().endswith(finding.check_code.split(".", 1)[1]))

    def test_testssl_full_coverage_is_not_silently_dropped(self):
        """Protocol, certificate, HSTS and vulnerability sections must all
        survive parsing; a cipher-only report is the regression this guards."""
        from scanners.parsers.testssl import parse_testssl_json

        expected = {
            "TLS1_0",
            "cert_expirationStatus",
            "HSTS_time",
            "heartbleed",
        }
        parsed = parse_testssl_json(TESTSSL_FULL_COVERAGE_JSON)
        self.assertEqual({item["id"] for item in parsed}, expected)

        outcome, _ = _execute(
            testssl_scanner, _run(stdout=TESTSSL_FULL_COVERAGE_JSON)
        )
        self.assertEqual(
            {finding.check_code for finding in outcome.findings},
            {f"testssl.{check_id}" for check_id in expected},
        )
        self.assertEqual(outcome.result.details["total_checks"], 4)

    def test_dnsrecon_records_are_grouped(self):
        outcome, _ = _execute(dnsrecon_scanner, _run(stdout=DNSRECON_JSON))
        codes = {finding.check_code for finding in outcome.findings}
        self.assertIn("dnsrecon.a_records", codes)
        self.assertIn("dnsrecon.mx_records", codes)

    def test_gobuster_paths_are_classified(self):
        outcome, _ = _execute(gobuster_scanner, _run(stdout=GOBUSTER_TEXT))
        admin = next(
            f for f in outcome.findings if f.check_code == "gobuster.path.admin"
        )
        self.assertEqual(admin.severity, "high")
        self.assertEqual(admin.status, FindingStatus.FAIL)
        self.assertEqual(admin.evidence["status_code"], 301)

    def test_gobuster_garbage_lines_are_ignored(self):
        output = (
            "===============================================================\n"
            "Gobuster v3.6\n"
            "Error: the server returned a 404\n"
            "/real (Status: 200) [Size: 12]\n"
        )
        outcome, _ = _execute(gobuster_scanner, _run(stdout=output))
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.findings[0].check_code, "gobuster.path.real")

    def test_gobuster_ansi_progress_prefix_does_not_hide_a_result(self):
        # Observed with Gobuster 3.6 in the sandbox image, even with
        # --no-color and no TTY: the result line is prefixed by ESC[2K.
        output = "\r\x1b[2K/admin                (Status: 200) [Size: 27]\n"
        outcome, _ = _execute(gobuster_scanner, _run(stdout=output))
        self.assertEqual(len(outcome.findings), 1)
        self.assertEqual(outcome.findings[0].check_code, "gobuster.path.admin")


class GobusterSoft404Tests(SimpleTestCase):
    """A catch-all 200 page must not make Gobuster refuse the whole run."""

    @patch.object(
        gobuster_module,
        "probe_soft_404",
        return_value=gobuster_module.Soft404Probe(
            sampled_path="/.presence-soft404-test",
            status_code=200,
            excluded_length=1234,
        ),
    )
    def test_detected_soft_404_is_passed_to_gobuster(self, probe):
        command = gobuster_scanner.build_command(
            "https://example.com", soft404_length=1234
        )

        self.assertIn("--exclude-length", command)
        self.assertEqual(command[command.index("--exclude-length") + 1], "1234")

    @patch.object(
        gobuster_module,
        "probe_soft_404",
        return_value=gobuster_module.Soft404Probe(
            sampled_path="/.presence-soft404-test", status_code=404
        ),
    )
    def test_real_404_does_not_exclude_any_length(self, probe):
        command = gobuster_scanner.build_command("https://example.com")

        self.assertNotIn("--exclude-length", command)

    def test_soft_404_probe_is_recorded_in_the_outcome(self):
        outcome, recorder = _execute(
            gobuster_scanner,
            _run(stdout=""),
            probe=gobuster_module.Soft404Probe(
                sampled_path="/.presence-soft404-test",
                status_code=200,
                excluded_length=1234,
            ),
        )

        self.assertEqual(recorder.calls, 1)
        self.assertEqual(outcome.result.details["soft_404_excluded_length"], 1234)
        self.assertEqual(
            outcome.result.details["soft_404_probe"]["sampled_path"],
            "/.presence-soft404-test",
        )
        self.assertTrue(outcome.result.details["scan_complete"])


class AdvancedScannerGracefulDegradationTests(SimpleTestCase):
    """A missing tool or a missing image never raises."""

    def test_sandbox_error_becomes_an_unavailable_outcome(self):
        from scanners.executors.sandbox import SandboxUnavailableError

        error = SandboxUnavailableError("image not present")
        for scanner in ADVANCED_SCANNERS:
            with self.subTest(scanner=scanner.name):
                outcome, recorder = _execute(scanner, _run(), error=error)
                details = outcome.result.details
                self.assertTrue(details["unavailable"])
                self.assertFalse(details["scan_complete"])
                self.assertEqual(details["partial_reason"], "sandbox_unavailable")
                self.assertEqual(recorder.calls, 1)
                self.assertTrue(
                    any(
                        f.check_code.endswith(".sandbox_unavailable")
                        for f in outcome.findings
                    )
                )


@override_settings(
    SCANNER_SANDBOX={
        "mode": "docker",
        "default_timeout": 60,
        "max_timeout": 300,
        "max_output_bytes": 1024 * 1024,
        "max_concurrency": 0,
        "docker": {
            "binary": "docker",
            "network": "presence_scanner_sandbox",
            "cpus": 1.0,
            "pids_limit": 128,
            "pull_policy": "never",
            "images": {
                "nmap": "presence-scanner-tools:2026-10-27",
            },
        },
    }
)
class AdvancedScannerOrchestrationTests(TestCase):
    """The orchestrator must propagate the adapters' completeness honestly."""

    def setUp(self):
        from accounts.models import User
        from websites.models import Website

        self.user = User.objects.create_user(
            "advanced-adapters@example.com", "CorrectHorseBattery1!"
        )
        self.website = Website.objects.create(
            owner=self.user, domain="example.com"
        )

    def _run_scan(self, run: ToolRun):
        from scans.models import Scan
        from scans.services.orchestrator import ScanOrchestrator
        from scanners.implementations.nmap import NmapScanner

        scan = Scan.objects.create(
            website=self.website, scan_type="security", status=Scan.Status.QUEUED
        )
        step = {
            "key": "nmap",
            "label": "Port Scan (Nmap)",
            "scanner": "nmap",
            "weight": 100,
            "required": True,
            "status": "pending",
            "progress": 0,
            "duration_ms": None,
            "error": None,
        }
        recorder = _Recorder()

        def _runner(*args, **kwargs):
            recorder.calls += 1
            return run

        # ``is_available`` is patched because the test worker has no Docker
        # socket; the adapter itself is the real nmap implementation.
        with patch(
            "scans.services.steps_builder.build_initial_steps", return_value=[step]
        ), patch(
            "scanners.security.target_validator.validate_target",
            return_value=_target(),
        ), patch.object(
            NmapScanner, "is_available", return_value=True
        ), patch.object(
            nmap_module, "run_tool", _runner
        ), patch(
            "scans.services.scoring.recalculate_scan_health"
        ):
            ScanOrchestrator(scan.id).run()

        scan.refresh_from_db()
        return scan, recorder

    def test_complete_run_is_completed_and_executes_once(self):
        scan, runner = self._run_scan(_run(stdout=NMAP_XML, stderr="Nmap done"))
        self.assertEqual(runner.calls, 1)
        self.assertEqual(scan.status, "completed")
        step = next(s for s in scan.steps if s["key"] == "nmap")
        self.assertEqual(step["status"], "completed")
        run = scan.scanner_runs.get(scanner="nmap")
        self.assertEqual(run.status, "completed")
        self.assertTrue(run.metadata["scan_complete"])

    def test_timeout_is_never_reported_as_completed(self):
        scan, runner = self._run_scan(
            _run(
                stdout=NMAP_XML,
                timed_out=True,
                exit_code=-1,
                killed_reason="timeout",
            )
        )
        self.assertEqual(runner.calls, 1)
        self.assertNotEqual(scan.status, "completed")
        step = next(s for s in scan.steps if s["key"] == "nmap")
        self.assertEqual(step["status"], "timeout")
        run = scan.scanner_runs.get(scanner="nmap")
        self.assertEqual(run.status, "timeout")
        self.assertFalse(run.metadata["scan_complete"])

    def test_partial_run_is_partial_and_keeps_its_reason(self):
        scan, runner = self._run_scan(
            _run(stdout=NMAP_XML, exit_code=1)
        )
        self.assertEqual(runner.calls, 1)
        self.assertNotEqual(scan.status, "completed")
        step = next(s for s in scan.steps if s["key"] == "nmap")
        self.assertEqual(step["status"], "partial")
        run = scan.scanner_runs.get(scanner="nmap")
        self.assertEqual(run.status, "partial")
        self.assertEqual(run.metadata["partial_reason"], "exit_code_1")
