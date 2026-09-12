"""dnsrecon DNS reconnaissance adapter."""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

from scanners.base import BaseScanner, NormalizedFinding, Severity, FindingStatus, ScanResult, ScannerType
from scanners.executors.command import default_executor
from scanners.exceptions import TargetValidationError
from scanners.security.target_validator import validate_domain

logger = logging.getLogger(__name__)


def _parse_dnsrecon_json(output: str) -> list[dict[str, Any]]:
    """Parse dnsrecon JSON output."""
    if not output.strip():
        return []
    try:
        data = json.loads(output)
        if isinstance(data, list):
            return data
        return data.get("results", [])
    except (json.JSONDecodeError, KeyError):
        return []


class DnsreconScanner(BaseScanner):
    """dnsrecon DNS reconnaissance adapter."""

    name = "dnsrecon"
    scanner_type = ScannerType.CLI
    _binary = "dnsrecon"

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("dnsrecon", {}).get("timeout", 60)

    def scan(self, domain: str) -> ScanResult:
        if not self.is_available():
            return self._create_result(
                score=None,
                status="neutral",
                message="dnsrecon not available — skipped",
                recommendation="Install dnsrecon for comprehensive DNS reconnaissance.",
            )

        try:
            validated = validate_domain(domain)
        except TargetValidationError as exc:
            return self._create_result(score=None, status="critical", message=str(exc))

        result = default_executor.run(
            command=self.build_command(validated),
            timeout=self.timeout,
            scanner_name=self.name,
        )

        parsed = _parse_dnsrecon_json(result.stdout)
        return self._create_result(
            score=None,
            status="neutral",
            message=f"dnsrecon found {len(parsed)} DNS record(s)",
            duration_ms=result.duration_ms,
            record_count=len(parsed),
        )

    def scan_findings(self, domain: str) -> list[NormalizedFinding]:
        if not self.is_available():
            return [NormalizedFinding(
                check_code="dnsrecon.unavailable",
                category="dns",
                severity=Severity.INFO,
                status=FindingStatus.NOT_APPLICABLE,
                title="dnsrecon not available",
                recommendation="Install dnsrecon for DNS reconnaissance.",
            )]

        try:
            validated = validate_domain(domain)
        except TargetValidationError as exc:
            return [NormalizedFinding(
                check_code="dnsrecon.target_validation",
                category="dns",
                severity=Severity.HIGH,
                status=FindingStatus.FAIL,
                title="Target validation failed",
                description=str(exc),
            )]

        result = default_executor.run(
            command=self.build_command(validated),
            timeout=self.timeout,
            scanner_name=self.name,
        )

        if result.timed_out:
            return [NormalizedFinding(
                check_code="dnsrecon.timeout",
                category="dns",
                severity=Severity.INFO,
                status=FindingStatus.UNKNOWN,
                title=f"dnsrecon timed out after {self.timeout}s",
                duration_ms=result.duration_ms,
            )]

        parsed = _parse_dnsrecon_json(result.stdout)
        return self.normalize(parsed)

    def build_command(self, target: str, options: dict | None = None) -> list[str]:
        return [
            "dnsrecon",
            "-d", target,
            "-t", "std",       # Standard enumeration
            "-j", "/dev/stdout",  # JSON to stdout
            "--lifetime", "10",
        ]

    def parse(self, output: str) -> list[dict[str, Any]]:
        return _parse_dnsrecon_json(output)

    def normalize(self, parsed_results: list[dict[str, Any]]) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        record_types = {}
        for record in parsed_results:
            rtype = str(record.get("type", "")).upper()
            record_types.setdefault(rtype, []).append(record)

        for rtype, records in record_types.items():
            findings.append(NormalizedFinding(
                check_code=f"dnsrecon.{rtype.lower()}_records",
                category="dns",
                severity=Severity.INFO,
                status=FindingStatus.PASS,
                title=f"DNS {rtype} records ({len(records)} found)",
                evidence={"records": records[:20]},  # Cap to avoid huge payloads
            ))

        return findings


dnsrecon_scanner = DnsreconScanner()
