"""Nmap scanner adapter.

Runs Nmap for port scanning and service detection.  Uses XML output
(``-oX -``) for structured parsing.

Security
--------
* Target is the pre-validated, SSRF-safe hostname passed as a separate
  list element — never interpolated into a shell command string.
* ``shell=False`` is enforced by :class:`~scanners.executors.command.CommandExecutor`.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from scanners.base import BaseScanner, NormalizedFinding, Severity, FindingStatus, ScanResult, ScannerType
from scanners.executors.command import CommandExecutor, default_executor
from scanners.exceptions import ScannerUnavailableError, TargetValidationError
from scanners.parsers.nmap import parse_nmap_xml
from scanners.security.target_validator import validate_target

logger = logging.getLogger(__name__)

# Default Nmap flags for service detection scan.
# We deliberately avoid -O (OS detection) which requires root.
_DEFAULT_NMAP_FLAGS = [
    "-sV",       # Service/version detection
    "-sT",       # TCP connect scan (no root required)
    "--top-ports", "1000",
    "--open",    # Only show open ports
    "-oX", "-",  # XML to stdout
    "-T4",       # Aggressive timing (safe for remote)
    "--host-timeout", "90s",
]

# NSE scripts to run for security checks (safe, non-intrusive)
_NSE_SCRIPTS = [
    "ssl-cert",
    "ssl-enum-ciphers",
    "http-security-headers",
    "http-methods",
]


class NmapScanner(BaseScanner):
    """Nmap port/service scanner adapter."""

    name = "nmap"
    scanner_type = ScannerType.CLI
    _binary = "nmap"

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("nmap", {}).get("timeout", 120)

    def scan(self, domain: str) -> ScanResult:
        """Run Nmap against *domain* and return an aggregated ScanResult.

        This method is used by the legacy public_checker flow.
        The orchestrator uses ``scan_findings()`` instead.
        """
        if not self.is_available():
            return self._create_result(
                score=None,
                status="neutral",
                message="Nmap not available — skipped",
                recommendation="Install nmap to enable port scanning.",
            )

        try:
            target_info = validate_target(f"https://{domain}")
        except TargetValidationError as exc:
            return self._create_result(
                score=None,
                status="critical",
                message=str(exc),
                recommendation="Provide a valid public domain.",
            )

        result = default_executor.run(
            command=self._build_nmap_command(target_info.safe_ips[0]),
            timeout=self.timeout,
            scanner_name=self.name,
        )

        if result.timed_out:
            return self._create_result(
                score=None,
                status="neutral",
                message=f"Nmap timed out after {self.timeout}s",
                recommendation="",
                duration_ms=result.duration_ms,
            )

        parsed = parse_nmap_xml(result.stdout)
        open_ports = [p for p in parsed if p.get("state") == "open"]

        return self._create_result(
            score=None,
            status="neutral",
            message=f"Nmap found {len(open_ports)} open port(s)",
            duration_ms=result.duration_ms,
            open_ports=len(open_ports),
            ports=open_ports,
            exit_code=result.exit_code,
        )

    def scan_findings(self, domain: str) -> list[NormalizedFinding]:
        """Run Nmap and return granular NormalizedFinding instances."""
        if not self.is_available():
            return [NormalizedFinding(
                check_code="nmap.unavailable",
                category="security",
                severity=Severity.INFO,
                status=FindingStatus.NOT_APPLICABLE,
                title="Nmap not available",
                description="The nmap binary was not found on PATH.",
                recommendation="Install nmap to enable port scanning.",
            )]

        try:
            target_info = validate_target(f"https://{domain}")
        except TargetValidationError as exc:
            return [NormalizedFinding(
                check_code="nmap.target_validation",
                category="security",
                severity=Severity.HIGH,
                status=FindingStatus.FAIL,
                title="Target validation failed",
                description=str(exc),
            )]

        result = default_executor.run(
            command=self._build_nmap_command(target_info.safe_ips[0]),
            timeout=self.timeout,
            scanner_name=self.name,
        )

        if result.timed_out:
            return [NormalizedFinding(
                check_code="nmap.timeout",
                category="security",
                severity=Severity.INFO,
                status=FindingStatus.UNKNOWN,
                title=f"Nmap scan timed out after {self.timeout}s",
                duration_ms=result.duration_ms,
            )]

        parsed = parse_nmap_xml(result.stdout)
        return self.normalize(parsed)

    def build_command(self, target: str, options: dict | None = None) -> list[str]:
        return self._build_nmap_command(target, options)

    def parse(self, output: str) -> list[dict[str, Any]]:
        return parse_nmap_xml(output)

    def normalize(self, parsed_results: list[dict[str, Any]]) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []

        open_ports = [p for p in parsed_results if p.get("state") == "open"]
        closed_ports = [p for p in parsed_results if p.get("state") != "open"]

        if not parsed_results:
            findings.append(NormalizedFinding(
                check_code="nmap.no_results",
                category="security",
                severity=Severity.INFO,
                status=FindingStatus.UNKNOWN,
                title="No Nmap results",
                description="Nmap returned no port data.",
            ))
            return findings

        # Open ports
        for port_data in open_ports:
            port = port_data.get("port", 0)
            service = port_data.get("service", {})
            service_name = service.get("name", "")
            product = service.get("product", "")
            version = service.get("version", "")

            # Flag unexpected open ports
            expected_web_ports = {80, 443, 8080, 8443}
            severity = Severity.INFO if port in expected_web_ports else Severity.MEDIUM

            findings.append(NormalizedFinding(
                check_code=f"nmap.open_port.{port}",
                category="security",
                severity=severity,
                status=FindingStatus.WARNING if port not in expected_web_ports else FindingStatus.PASS,
                title=f"Port {port}/{port_data.get('protocol', 'tcp')} open — {service_name}",
                description=f"Port {port} is open running {product} {version}".strip(),
                evidence=port_data,
                recommendation=(
                    f"Review whether port {port} should be publicly accessible."
                    if port not in expected_web_ports else ""
                ),
            ))

        # Summarise findings
        findings.append(NormalizedFinding(
            check_code="nmap.open_ports_summary",
            category="security",
            severity=Severity.INFO,
            status=FindingStatus.PASS,
            title=f"Nmap scan complete: {len(open_ports)} open port(s)",
            evidence={"open_ports": len(open_ports), "total_scanned": len(parsed_results)},
        ))

        return findings

    def _build_nmap_command(self, target_ip: str, options: dict | None = None) -> list[str]:
        """Build Nmap command. *target_ip* is a pre-validated IP address."""
        cfg = getattr(settings, "SCANNER_CONFIG", {}).get("nmap", {})
        nse_enabled = cfg.get("nse_enabled", False)

        cmd = ["nmap", *_DEFAULT_NMAP_FLAGS]

        if nse_enabled:
            cmd.extend(["--script", ",".join(_NSE_SCRIPTS)])

        # Target MUST be the last argument, separated by --
        cmd.extend(["--", target_ip])
        return cmd


nmap_scanner = NmapScanner()
