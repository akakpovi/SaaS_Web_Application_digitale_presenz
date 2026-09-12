"""Gobuster directory/file brute-force scanner adapter."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from scanners.base import BaseScanner, NormalizedFinding, Severity, FindingStatus, ScanResult, ScannerType
from scanners.executors.command import default_executor
from scanners.exceptions import TargetValidationError
from scanners.security.target_validator import validate_target

logger = logging.getLogger(__name__)


def _parse_gobuster_output(output: str) -> list[dict[str, Any]]:
    """Parse Gobuster plain text output."""
    findings: list[dict[str, Any]] = []
    for line in output.splitlines():
        line = line.strip()
        # Gobuster dir output: "/path (Status: 200) [Size: 1234]"
        if line.startswith("/") or line.startswith("http"):
            status_code = 0
            size = 0
            path = line
            if "(Status:" in line:
                parts = line.split()
                path = parts[0] if parts else line
                for i, part in enumerate(parts):
                    if part == "(Status:":
                        try:
                            status_code = int(parts[i + 1].rstrip(")"))
                        except (IndexError, ValueError):
                            pass
                    if part == "[Size:":
                        try:
                            size = int(parts[i + 1].rstrip("]"))
                        except (IndexError, ValueError):
                            pass
            findings.append({
                "path": path,
                "status_code": status_code,
                "size": size,
            })
    return findings


class GobusterScanner(BaseScanner):
    """Gobuster directory enumeration scanner adapter."""

    name = "gobuster"
    scanner_type = ScannerType.CLI
    _binary = "gobuster"

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("gobuster", {}).get("timeout", 120)

    def scan(self, domain: str) -> ScanResult:
        if not self.is_available():
            return self._create_result(
                score=None,
                status="neutral",
                message="Gobuster not available — skipped",
                recommendation="Install gobuster for directory enumeration.",
            )

        try:
            target_info = validate_target(f"https://{domain}")
        except TargetValidationError as exc:
            return self._create_result(score=None, status="critical", message=str(exc))

        result = default_executor.run(
            command=self.build_command(target_info.url),
            timeout=self.timeout,
            scanner_name=self.name,
        )

        parsed = _parse_gobuster_output(result.stdout)
        return self._create_result(
            score=None,
            status="neutral",
            message=f"Gobuster found {len(parsed)} path(s)",
            duration_ms=result.duration_ms,
            paths_found=len(parsed),
        )

    def scan_findings(self, domain: str) -> list[NormalizedFinding]:
        if not self.is_available():
            return [NormalizedFinding(
                check_code="gobuster.unavailable",
                category="security",
                severity=Severity.INFO,
                status=FindingStatus.NOT_APPLICABLE,
                title="Gobuster not available",
                recommendation="Install gobuster for directory enumeration.",
            )]

        try:
            target_info = validate_target(f"https://{domain}")
        except TargetValidationError as exc:
            return [NormalizedFinding(
                check_code="gobuster.target_validation",
                category="security",
                severity=Severity.HIGH,
                status=FindingStatus.FAIL,
                title="Target validation failed",
                description=str(exc),
            )]

        result = default_executor.run(
            command=self.build_command(target_info.url),
            timeout=self.timeout,
            scanner_name=self.name,
        )

        if result.timed_out:
            return [NormalizedFinding(
                check_code="gobuster.timeout",
                category="security",
                severity=Severity.INFO,
                status=FindingStatus.UNKNOWN,
                title=f"Gobuster timed out after {self.timeout}s",
                duration_ms=result.duration_ms,
            )]

        parsed = _parse_gobuster_output(result.stdout)
        return self.normalize(parsed)

    def build_command(self, target: str, options: dict | None = None) -> list[str]:
        cfg = getattr(settings, "SCANNER_CONFIG", {}).get("gobuster", {})
        wordlist = cfg.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        threads = cfg.get("threads", 10)
        return [
            "gobuster", "dir",
            "-u", target,
            "-w", wordlist,
            "-t", str(threads),
            "-q",  # Quiet
            "-n",  # No status codes in output (cleaner)
            "--timeout", "10s",
            "--no-error",
        ]

    def parse(self, output: str) -> list[dict[str, Any]]:
        return _parse_gobuster_output(output)

    def normalize(self, parsed_results: list[dict[str, Any]]) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        # Sensitive paths
        sensitive = {"/admin", "/.env", "/backup", "/config", "/.git", "/wp-admin"}

        for item in parsed_results:
            path = item.get("path", "")
            severity = Severity.HIGH if path in sensitive else Severity.LOW
            status = FindingStatus.FAIL if path in sensitive else FindingStatus.WARNING

            findings.append(NormalizedFinding(
                check_code=f"gobuster.path.{path.strip('/').replace('/', '_') or 'root'}",
                category="security",
                severity=severity,
                status=status,
                title=f"Directory/file found: {path}",
                description=f"Path '{path}' is publicly accessible (HTTP {item.get('status_code', '?')})",
                evidence=item,
                recommendation=(
                    f"Restrict access to '{path}' or remove it if not needed."
                    if path in sensitive else ""
                ),
            ))

        return findings


gobuster_scanner = GobusterScanner()
