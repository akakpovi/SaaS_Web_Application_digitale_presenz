"""Nikto web vulnerability scanner adapter."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from scanners.base import BaseScanner, NormalizedFinding, Severity, FindingStatus, ScanResult, ScannerType
from scanners.executors.command import default_executor
from scanners.exceptions import TargetValidationError
from scanners.parsers.nikto import parse_nikto_json, parse_nikto_text
from scanners.security.target_validator import validate_target

logger = logging.getLogger(__name__)


class NiktoScanner(BaseScanner):
    """Nikto web vulnerability scanner adapter."""

    name = "nikto"
    scanner_type = ScannerType.CLI
    _binary = "nikto"

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("nikto", {}).get("timeout", 180)

    def scan(self, domain: str) -> ScanResult:
        if not self.is_available():
            return self._create_result(
                score=None,
                status="neutral",
                message="Nikto not available — skipped",
                recommendation="Install nikto to enable web vulnerability scanning.",
            )

        try:
            target_info = validate_target(f"https://{domain}")
        except TargetValidationError as exc:
            return self._create_result(score=None, status="critical", message=str(exc))

        result = default_executor.run(
            command=self.build_command(target_info.hostname),
            timeout=self.timeout,
            scanner_name=self.name,
        )

        parsed = parse_nikto_json(result.stdout) or parse_nikto_text(result.stdout)
        return self._create_result(
            score=None,
            status="neutral",
            message=f"Nikto found {len(parsed)} issue(s)",
            duration_ms=result.duration_ms,
            findings_count=len(parsed),
        )

    def scan_findings(self, domain: str) -> list[NormalizedFinding]:
        if not self.is_available():
            return [NormalizedFinding(
                check_code="nikto.unavailable",
                category="security",
                severity=Severity.INFO,
                status=FindingStatus.NOT_APPLICABLE,
                title="Nikto not available",
                recommendation="Install nikto to enable web vulnerability scanning.",
            )]

        try:
            target_info = validate_target(f"https://{domain}")
        except TargetValidationError as exc:
            return [NormalizedFinding(
                check_code="nikto.target_validation",
                category="security",
                severity=Severity.HIGH,
                status=FindingStatus.FAIL,
                title="Target validation failed",
                description=str(exc),
            )]

        result = default_executor.run(
            command=self.build_command(target_info.hostname),
            timeout=self.timeout,
            scanner_name=self.name,
        )

        if result.timed_out:
            return [NormalizedFinding(
                check_code="nikto.timeout",
                category="security",
                severity=Severity.INFO,
                status=FindingStatus.UNKNOWN,
                title=f"Nikto timed out after {self.timeout}s",
                duration_ms=result.duration_ms,
            )]

        parsed = parse_nikto_json(result.stdout) or parse_nikto_text(result.stdout)
        return self.normalize(parsed)

    def build_command(self, target: str, options: dict | None = None) -> list[str]:
        return [
            "nikto",
            "-h", target,
            "-Format", "json",
            "-nointeractive",
            "-timeout", "10",
            "-maxtime", str(self.timeout),
        ]

    def parse(self, output: str) -> list[dict[str, Any]]:
        return parse_nikto_json(output) or parse_nikto_text(output)

    def normalize(self, parsed_results: list[dict[str, Any]]) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        for item in parsed_results:
            msg = item.get("msg", "")
            osvdb = item.get("osvdb", "")
            url = item.get("url", "")
            ref = item.get("references", "")

            findings.append(NormalizedFinding(
                check_code=f"nikto.{item.get('id', 'finding')}",
                category="security",
                severity=Severity.MEDIUM,
                status=FindingStatus.FAIL,
                title=msg[:255] if msg else "Nikto finding",
                description=msg,
                evidence=item,
                recommendation="Review the reported issue and apply appropriate remediation.",
                reference_url=ref or (f"https://osvdb.org/{osvdb}" if osvdb else ""),
            ))
        return findings


nikto_scanner = NiktoScanner()
