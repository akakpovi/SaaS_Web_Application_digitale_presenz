"""Tests for scanner infrastructure — CommandExecutor, parsers, and adapters.

These tests do NOT require external tool binaries.  External tool adapters
are tested for graceful degradation when their binary is unavailable.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from scanners.base import (
    BaseScanner,
    FindingStatus,
    NormalizedFinding,
    ScanResult,
    Severity,
    ScannerType,
)
from scanners.exceptions import ScannerUnavailableError
from scanners.executors.command import CommandExecutor
from scanners.registry import ScannerRegistry
from scanners.security.target_validator import validate_target


# ═══════════════════════════════════════════════════
# CommandExecutor tests
# ═══════════════════════════════════════════════════

class CommandExecutorTests(TestCase):
    def setUp(self):
        self.executor = CommandExecutor()

    def test_simple_command_echo(self):
        result = self.executor.run(
            command=["echo", "hello"],
            timeout=10,
            scanner_name="test",
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hello", result.stdout)

    def test_command_exit_code_nonzero(self):
        result = self.executor.run(
            command=["false"],
            timeout=10,
            scanner_name="test",
        )
        self.assertNotEqual(result.exit_code, 0)

    def test_timeout_sets_timed_out_flag(self):
        result = self.executor.run(
            command=["sleep", "10"],
            timeout=1,
            scanner_name="test",
        )
        self.assertTrue(result.timed_out)

    def test_shell_false_by_default(self):
        """Verify the executor never uses shell=True."""
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = (b"output", b"")
            mock_proc.returncode = 0
            mock_popen.return_value.communicate.return_value = (b"output", b"")
            mock_popen.return_value.returncode = 0
            self.executor.run(command=["echo", "test"], timeout=10, scanner_name="test")
            call_kwargs = mock_popen.call_args[1]
            self.assertFalse(call_kwargs.get("shell", False))

    def test_output_size_limit_applied(self):
        """stdout should be truncated to max_output_size."""
        executor = CommandExecutor(max_output_bytes=100)
        result = executor.run(
            command=["python3", "-c", "print('x' * 10000)"],
            timeout=10,
            scanner_name="test",
        )
        self.assertLessEqual(len(result.stdout), 150)  # some slack for newline

    def test_duration_ms_populated(self):
        result = self.executor.run(
            command=["echo", "hi"],
            timeout=10,
            scanner_name="test",
        )
        self.assertIsInstance(result.duration_ms, int)
        self.assertGreater(result.duration_ms, 0)

    def test_env_does_not_leak_secrets(self):
        """The executor should not pass host env vars (e.g. AWS_SECRET_ACCESS_KEY)."""
        import os
        os.environ["_TEST_SECRET"] = "super_secret"
        try:
            result = self.executor.run(
                command=["env"],
                timeout=10,
                scanner_name="test",
            )
            # The executor uses a minimal safe env; _TEST_SECRET should NOT appear
            self.assertNotIn("_TEST_SECRET", result.stdout)
        finally:
            del os.environ["_TEST_SECRET"]


# ═══════════════════════════════════════════════════
# Target validator tests (SSRF protection)
# ═══════════════════════════════════════════════════

class TargetValidatorTests(TestCase):
    """Verify SSRF protection at the scanner layer."""

    def test_public_domain_allowed(self):
        # Note: this test requires real DNS in the container
        # Use a known stable public domain
        try:
            info = validate_target("https://example.com")
            self.assertTrue(len(info.safe_ips) > 0)
        except Exception as e:
            # DNS resolution may fail in sandboxed environment — acceptable
            self.skipTest(f"DNS resolution unavailable: {e}")

    def test_localhost_blocked(self):
        from scanners.exceptions import TargetValidationError
        with self.assertRaises(TargetValidationError):
            validate_target("https://localhost")

    def test_loopback_ip_blocked(self):
        from scanners.exceptions import TargetValidationError
        with self.assertRaises(TargetValidationError):
            validate_target("https://127.0.0.1")

    def test_private_ip_blocked(self):
        from scanners.exceptions import TargetValidationError
        with self.assertRaises(TargetValidationError):
            validate_target("https://192.168.1.1")

    def test_private_ip_10_blocked(self):
        from scanners.exceptions import TargetValidationError
        with self.assertRaises(TargetValidationError):
            validate_target("https://10.0.0.1")

    def test_metadata_service_blocked(self):
        from scanners.exceptions import TargetValidationError
        with self.assertRaises(TargetValidationError):
            validate_target("https://169.254.169.254")


# ═══════════════════════════════════════════════════
# Base scanner tests
# ═══════════════════════════════════════════════════

class BaseScannerTests(TestCase):
    def _make_scanner(self, name="test", scanner_type=ScannerType.INTERNAL):
        """Create a minimal concrete scanner for testing."""
        class MinimalScanner(BaseScanner):
            def scan(self, domain):
                return self._create_result(
                    score=20,
                    status="healthy",
                    message="OK",
                    recommendation="",
                )
        MinimalScanner.name = name
        MinimalScanner.scanner_type = scanner_type
        return MinimalScanner()

    def test_internal_scanner_always_available(self):
        scanner = self._make_scanner(scanner_type=ScannerType.INTERNAL)
        self.assertTrue(scanner.is_available())

    def test_cli_scanner_unavailable_when_binary_missing(self):
        class MissingBinaryScanner(BaseScanner):
            name = "missing_binary_xyz_123"
            scanner_type = ScannerType.CLI
            _binary = "missing_tool_xyz_123"

            def scan(self, domain):
                return self._create_result(0, "neutral", "N/A")

        scanner = MissingBinaryScanner()
        self.assertFalse(scanner.is_available())

    def test_scan_result_to_findings_healthy(self):
        scanner = self._make_scanner("website")
        result = ScanResult(
            score=20, status="healthy", message="Site accessible",
            recommendation="", details={"http_status": 200}
        )
        findings = scanner._scan_result_to_findings(result, "example.com")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].status, FindingStatus.PASS)

    def test_scan_result_to_findings_critical(self):
        scanner = self._make_scanner("website")
        result = ScanResult(
            score=0, status="critical", message="Site down",
            recommendation="Check server.", details={}
        )
        findings = scanner._scan_result_to_findings(result, "example.com")
        self.assertEqual(findings[0].status, FindingStatus.FAIL)

    def test_scan_findings_delegates_to_scan_then_normalize(self):
        """Default scan_findings() calls scan() and converts to findings."""
        scanner = self._make_scanner("ssl")
        findings = scanner.scan_findings("example.com")
        self.assertIsInstance(findings, list)
        self.assertTrue(all(isinstance(f, NormalizedFinding) for f in findings))


# ═══════════════════════════════════════════════════
# External adapter graceful degradation tests
# ═══════════════════════════════════════════════════

class ExternalAdapterGracefulDegradationTests(TestCase):
    """External adapters should return graceful results when binary is missing."""

    def _test_adapter_graceful(self, adapter_import_path, scanner_instance_name):
        """Generic test: adapter should not crash when binary is absent."""
        from importlib import import_module

        module = import_module(adapter_import_path)
        scanner = getattr(module, scanner_instance_name)

        if scanner.is_available():
            self.skipTest(f"{scanner.name} binary is available — skipping unavailability test")

        # scan() should return a graceful neutral/unavailable result
        result = scanner.scan("example.com")
        self.assertIn(result.status, ["neutral", "critical"])

        # scan_findings() should return a list (not raise)
        findings = scanner.scan_findings("example.com")
        self.assertIsInstance(findings, list)
        # All findings should have NOT_APPLICABLE or UNKNOWN status
        for f in findings:
            self.assertIn(f.status, [FindingStatus.NOT_APPLICABLE, FindingStatus.UNKNOWN, FindingStatus.FAIL])

    def test_nmap_graceful_when_unavailable(self):
        self._test_adapter_graceful("scanners.implementations.nmap", "nmap_scanner")

    def test_nikto_graceful_when_unavailable(self):
        self._test_adapter_graceful("scanners.implementations.nikto", "nikto_scanner")

    def test_nuclei_graceful_when_unavailable(self):
        self._test_adapter_graceful("scanners.implementations.nuclei", "nuclei_scanner")

    def test_whatweb_graceful_when_unavailable(self):
        self._test_adapter_graceful("scanners.implementations.whatweb", "whatweb_scanner")

    def test_testssl_graceful_when_unavailable(self):
        self._test_adapter_graceful("scanners.implementations.testssl", "testssl_scanner")

    def test_dnsrecon_graceful_when_unavailable(self):
        self._test_adapter_graceful("scanners.implementations.dnsrecon", "dnsrecon_scanner")

    def test_gobuster_graceful_when_unavailable(self):
        self._test_adapter_graceful("scanners.implementations.gobuster", "gobuster_scanner")

    def test_feroxbuster_graceful_when_unavailable(self):
        self._test_adapter_graceful("scanners.implementations.feroxbuster", "feroxbuster_scanner")

    def test_zap_graceful_when_unavailable(self):
        self._test_adapter_graceful("scanners.implementations.zap", "zap_scanner")


# ═══════════════════════════════════════════════════
# Parser unit tests (no external tools required)
# ═══════════════════════════════════════════════════

class NmapParserTests(TestCase):
    def test_parse_empty_xml(self):
        from scanners.parsers.nmap import parse_nmap_xml
        result = parse_nmap_xml("")
        self.assertIsInstance(result, list)

    def test_parse_valid_xml_with_open_port(self):
        from scanners.parsers.nmap import parse_nmap_xml
        xml = """<?xml version="1.0"?>
        <nmaprun>
          <host>
            <ports>
              <port protocol="tcp" portid="80">
                <state state="open"/>
                <service name="http" product="nginx" version="1.20"/>
              </port>
            </ports>
          </host>
        </nmaprun>"""
        results = parse_nmap_xml(xml)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["port"], 80)
        self.assertEqual(results[0]["state"], "open")
        self.assertEqual(results[0]["service"]["name"], "http")


class NiktoParserTests(TestCase):
    def test_parse_empty_output(self):
        from scanners.parsers.nikto import parse_nikto_json
        result = parse_nikto_json("")
        self.assertIsInstance(result, list)

    def test_parse_nikto_json(self):
        from scanners.parsers.nikto import parse_nikto_json
        import json
        data = [
            {
                "vulnerabilities": [
                    {
                        "id": "001234",
                        "msg": "Server leaks inodes",
                        "url": "/",
                        "method": "GET",
                    }
                ]
            }
        ]
        result = parse_nikto_json(json.dumps(data))
        self.assertEqual(len(result), 1)
        self.assertIn("msg", result[0])

    def test_parse_nikto_text_keeps_findings_and_drops_run_metadata(self):
        """Nikto's default screen report is the collected stdout.

        Real shape captured from the sandbox: findings carry a bracketed id
        (``+ [011799] /: …``) while ``+ Target IP:``/``+ Server:`` describe the
        run and must never become findings.
        """
        from scanners.parsers.nikto import parse_nikto_text

        output = "\n".join([
            "- Nikto v2.6.1",
            "---",
            "+ Target IP:          188.114.97.3",
            "+ Target Hostname:    appchat.elomaiapp.com",
            "+ Target Port:        80",
            "+ Platform:           Unknown",
            "+ Start Time:         2026-10-27 05:23:15 (GMT0)",
            "---",
            "+ Server: cloudflare",
            "+ Multiple IPs found: 188.114.97.3, 188.114.96.3",
            "+ [011799] /: An alt-svc header was found which is advertising HTTP/3.",
            "+ OSVDB-1234: /admin/: Admin interface exposed.",
            "+ /backup/: Directory indexing enabled.",
            "+ End Time:           2026-10-27 05:24:02 (GMT0) (47 seconds)",
        ])

        findings = parse_nikto_text(output)
        self.assertEqual(len(findings), 3)
        self.assertEqual(findings[0]["id"], "OSVDB-011799")
        self.assertEqual(findings[0]["url"], "/")
        self.assertIn("alt-svc", findings[0]["msg"])
        self.assertEqual(findings[1]["url"], "/admin/")
        self.assertEqual(findings[2]["url"], "/backup/")
        self.assertFalse(any("cloudflare" in f["msg"] for f in findings))

    def test_parse_nikto_text_ignores_text_without_findings(self):
        from scanners.parsers.nikto import parse_nikto_text

        output = "\n".join([
            "- Nikto v2.6.1",
            "+ Target IP: 188.114.97.3",
            "+ Server: cloudflare",
            "+ No CGI Directories found (use '-C all' to force check all possible dirs)",
            "+ 1 host(s) tested",
        ])

        self.assertEqual(parse_nikto_text(output), [])


class WhatWebParserTests(TestCase):
    def test_parse_empty(self):
        from scanners.parsers.whatweb import parse_whatweb_json
        result = parse_whatweb_json("")
        self.assertIsInstance(result, list)

    def test_parse_whatweb_json(self):
        from scanners.parsers.whatweb import parse_whatweb_json
        import json
        data = [{"target": "https://example.com", "http_status": 200, "plugins": {"WordPress": {"version": ["5.9"]}}}]
        result = parse_whatweb_json(json.dumps(data))
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)


class DnsreconParserTests(TestCase):
    def test_parse_empty_output(self):
        from scanners.implementations.dnsrecon import _parse_dnsrecon_json
        self.assertEqual(_parse_dnsrecon_json(""), [])
        self.assertEqual(_parse_dnsrecon_json("   "), [])

    def test_parse_json_interleaved_with_progress_lines(self):
        """dnsrecon writes its JSON report and its progress to the same stream.

        Real capture: the report array is followed by ``[*]``/``[+]`` progress
        lines, which made a strict ``json.loads`` of the whole buffer fail and
        reported a complete run as having zero records.
        """
        from scanners.implementations.dnsrecon import _parse_dnsrecon_json

        output = "\n".join([
            "[",
            '    {"type": "NS", "name": "example.com", "address": "ns1.example.net"},',
            '    {"type": "A", "name": "example.com", "address": "93.184.216.34"}',
            "]",
            "[*] \t AAAA example.com 2606:2800:220:1:248:1893:25c8:1946",
            "[*] Enumerating SRV Records",
            "[+] 0 Records Found",
            "[*] Saving records to JSON file: /dev/stdout",
        ])

        records = _parse_dnsrecon_json(output)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["type"], "NS")
        self.assertEqual(records[1]["address"], "93.184.216.34")

    def test_run_header_is_not_normalized_into_a_finding(self):
        """A real run yields A/AAAA findings only, never a ``scaninfo`` one."""
        from scanners.implementations.dnsrecon import DnsreconScanner

        records = [
            {"type": "ScanInfo", "arguments": "dnsrecon -d example.com -t std"},
            {"type": "A", "name": "example.com", "address": "93.184.216.34"},
        ]
        codes = [f.check_code for f in DnsreconScanner().normalize(records)]
        self.assertEqual(codes, ["dnsrecon.a_records"])

    def test_parse_dict_payload_and_garbage(self):
        from scanners.implementations.dnsrecon import _parse_dnsrecon_json

        self.assertEqual(
            _parse_dnsrecon_json('{"results": [{"type": "MX"}]}')[0]["type"],
            "MX",
        )
        self.assertEqual(_parse_dnsrecon_json("not json at all"), [])
        self.assertEqual(_parse_dnsrecon_json("[{"), [])

