"""Nmap scanner adapter.

Runs Nmap for port scanning and service detection.  Uses XML output
(``-oX -``) for structured parsing.

Security
--------
* Target is a pre-validated, SSRF-safe IP address passed as a separate
  list element — never interpolated into a shell command string.
* ``shell=False`` is enforced by the sandbox executor.

Completeness
------------
The run is reported as incomplete when the sandbox had to kill it, when Nmap
exited non-zero, when the report was truncated, or when Nmap itself skipped the
host after its ``--host-timeout`` elapsed (it still exits 0 in that case, and
that empty result must never resolve an existing finding).
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from scanners.base import (
    BaseScanner,
    FindingStatus,
    NormalizedFinding,
    ScanContext,
    ScanOutcome,
    ScanResult,
    ScannerType,
    Severity,
)
from scanners.exceptions import TargetValidationError
from scanners.implementations.tool_run import (
    SandboxError,
    ToolRun,
    build_outcome,
    evaluate_completeness,
    resolve_target,
    run_tool,
    target_validation_outcome,
    unavailable_outcome,
)
from scanners.parsers.nmap import parse_nmap_xml

logger = logging.getLogger(__name__)

# Default Nmap flags for service detection scan.
# We deliberately avoid -O (OS detection) which requires root.
_DEFAULT_NMAP_FLAGS = [
    "-sV",  # Service/version detection
    "-sT",  # TCP connect scan (no root required)
    "--top-ports",
    "1000",
    "--open",  # Only show open ports
    "-oX",
    "-",  # XML to stdout
    "-T4",  # Aggressive timing (safe for remote)
]

# NSE scripts to run for security checks (safe, non-intrusive)
_NSE_SCRIPTS = [
    "ssl-cert",
    "ssl-enum-ciphers",
    "http-security-headers",
    "http-methods",
]

#: Nmap exits 0 when it gives up on a host after this message; the port list is
#: then incomplete even though the process "succeeded".
_HOST_TIMEOUT_MARKERS = (
    "Skipping host",
    "host timeout",
    "giving up on",
)


class NmapScanner(BaseScanner):
    """Nmap port/service scanner adapter."""

    name = "nmap"
    scanner_type = ScannerType.CLI
    _binary = "nmap"

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("nmap", {}).get("timeout", 75)

    # ------------------------------------------------------------------
    # Single execution
    # ------------------------------------------------------------------

    def execute(
        self,
        domain: str,
        context: ScanContext | None = None,
    ) -> ScanOutcome:
        """Run Nmap exactly once and return result + normalized findings."""
        if not self.is_available():
            return build_outcome(
                self,
                run=ToolRun(exit_code=-1),
                findings=[
                    NormalizedFinding(
                        check_code="nmap.unavailable",
                        category="security",
                        severity=Severity.INFO,
                        status=FindingStatus.NOT_APPLICABLE,
                        title="Nmap not available",
                        description="The nmap binary was not found on PATH.",
                        recommendation="Install nmap to enable port scanning.",
                    )
                ],
                message="Nmap not available — skipped",
                status="neutral",
                recommendation="Install nmap to enable port scanning.",
                scan_complete=False,
                partial_reason="unavailable",
            )

        try:
            target_info = resolve_target(domain, context)
        except TargetValidationError as exc:
            return target_validation_outcome(self, error=str(exc))

        # Nmap probes a validated IP; the SSRF gate already resolved and
        # checked every address behind the hostname.
        target_ip = (target_info.safe_ips or [target_info.hostname])[0]

        try:
            run = run_tool(
                self,
                self._build_nmap_command(target_ip),
                context=context,
            )
        except SandboxError as exc:
            logger.error("Nmap sandbox unavailable: %s", exc)
            return unavailable_outcome(self, reason=str(exc))

        complete, reason = evaluate_completeness(run, ok_exit_codes=(0,))
        if complete and self._host_was_skipped(run):
            # Nmap exited 0 but dropped the host: the port list is partial.
            complete, reason = False, "host_timeout"
        if complete and not self._looks_like_nmap_xml(run.stdout):
            # The expected XML report is missing or truncated mid-document.
            complete, reason = False, "unparsable_report"

        parsed = parse_nmap_xml(run.stdout)
        findings = self.normalize(parsed)
        open_ports = [p for p in parsed if p.get("state") == "open"]

        return build_outcome(
            self,
            run=run,
            findings=findings,
            message=(
                f"Nmap found {len(open_ports)} open port(s)"
                if complete
                else f"Nmap scan incomplete ({reason}): "
                f"{len(open_ports)} open port(s) seen so far"
            ),
            status="neutral" if complete else "warning",
            scan_complete=complete,
            partial_reason=reason,
            open_ports=len(open_ports),
            ports=open_ports,
            raw_report=run.stdout or None,
            raw_report_format="nmap-xml",
            raw_report_meta={"open_ports": len(open_ports)},
        )

    @staticmethod
    def _host_was_skipped(run: ToolRun) -> bool:
        """True when Nmap dropped the target after its own host timeout."""
        text = run.stderr or ""
        return any(marker in text for marker in _HOST_TIMEOUT_MARKERS)

    @staticmethod
    def _looks_like_nmap_xml(output: str) -> bool:
        """Nmap always writes a complete ``<nmaprun>`` document to ``-oX -``."""
        text = output or ""
        return "<nmaprun" in text and "</nmaprun>" in text

    # ------------------------------------------------------------------
    # Legacy entry points (public_checker, direct callers)
    # ------------------------------------------------------------------

    def scan(self, domain: str) -> ScanResult:
        return self.execute(domain).result

    def scan_findings(
        self,
        domain: str,
        result: ScanResult | None = None,
    ) -> list[NormalizedFinding]:
        """Legacy entry point; the tool runs once via :meth:`execute`."""
        return self.execute(domain).findings

    def build_command(self, target: str, options: dict | None = None) -> list[str]:
        return self._build_nmap_command(target, options)

    def parse(self, output: str) -> list[dict[str, Any]]:
        return parse_nmap_xml(output)

    def normalize(
        self, parsed_results: list[dict[str, Any]]
    ) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []

        open_ports = [p for p in parsed_results if p.get("state") == "open"]
        expected_web_ports = {80, 443, 8080, 8443}

        # Open ports
        for port_data in open_ports:
            port = port_data.get("port", 0)
            service = port_data.get("service", {})
            service_name = service.get("name", "")
            product = service.get("product", "")
            version = service.get("version", "")

            findings.append(
                NormalizedFinding(
                    check_code=f"nmap.open_port.{port}",
                    category="security",
                    severity=Severity.INFO
                    if port in expected_web_ports
                    else Severity.MEDIUM,
                    status=FindingStatus.PASS
                    if port in expected_web_ports
                    else FindingStatus.WARNING,
                    title=f"Port {port}/{port_data.get('protocol', 'tcp')} open — {service_name}",
                    description=f"Port {port} is open running {product} {version}".strip(),
                    evidence=port_data,
                    recommendation=(
                        f"Review whether port {port} should be publicly accessible."
                        if port not in expected_web_ports
                        else ""
                    ),
                )
            )

        if parsed_results:
            findings.append(
                NormalizedFinding(
                    check_code="nmap.open_ports_summary",
                    category="security",
                    severity=Severity.INFO,
                    status=FindingStatus.PASS,
                    title=f"Nmap scan complete: {len(open_ports)} open port(s)",
                    evidence={
                        "open_ports": len(open_ports),
                        "total_scanned": len(parsed_results),
                    },
                )
            )
        else:
            # No XML at all: the report is unusable, not a proof of "no ports".
            findings.append(
                NormalizedFinding(
                    check_code="nmap.no_results",
                    category="security",
                    severity=Severity.INFO,
                    status=FindingStatus.UNKNOWN,
                    title="No Nmap results",
                    description="Nmap returned no port data.",
                )
            )

        return findings

    def _build_nmap_command(
        self, target_ip: str, options: dict | None = None
    ) -> list[str]:
        """Build the Nmap command. *target_ip* is a pre-validated IP address."""
        cfg = getattr(settings, "SCANNER_CONFIG", {}).get("nmap", {})
        nse_enabled = cfg.get("nse_enabled", False)
        # Nmap must stop scanning the host *before* the sandbox kills the
        # container, otherwise the XML report is lost and the run cannot even
        # prove what it had found.  One second of margin is not enough for a
        # large scan, so keep a tenth of the budget as headroom.
        host_timeout = max(5, int(self.timeout * 0.85))

        cmd = [*_DEFAULT_NMAP_FLAGS, "--host-timeout", f"{host_timeout}s"]

        if nse_enabled:
            cmd.extend(["--script", ",".join(_NSE_SCRIPTS)])

        # Target MUST be the last argument, separated by --
        cmd.extend(["--", target_ip])
        return ["nmap", *cmd]


nmap_scanner = NmapScanner()
