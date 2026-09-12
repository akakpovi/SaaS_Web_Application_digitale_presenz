"""Nuclei template-based vulnerability scanner adapter."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from scanners.base import BaseScanner, NormalizedFinding, Severity, FindingStatus, ScanResult, ScannerType
from scanners.executors.command import default_executor
from scanners.exceptions import TargetValidationError
from scanners.parsers.nuclei import parse_nuclei_jsonl
from scanners.security.target_validator import validate_target

logger = logging.getLogger(__name__)

_NUCLEI_SEVERITY_MAP = {
    "info": Severity.INFO,
    "low": Severity.LOW,
    "medium": Severity.MEDIUM,
    "high": Severity.HIGH,
    "critical": Severity.CRITICAL,
}


class NucleiScanner(BaseScanner):
    """Nuclei template scanner adapter."""

    name = "nuclei"
    scanner_type = ScannerType.CLI
    _binary = "nuclei"

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("nuclei", {}).get("timeout", 180)

    def scan(self, domain: str) -> ScanResult:
        if not self.is_available():
            return self._create_result(
                score=None,
                status="neutral",
                message="Nuclei not available — skipped",
                recommendation="Install nuclei to enable template-based scanning.",
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

        parsed = parse_nuclei_jsonl(result.stdout)
        return self._create_result(
            score=None,
            status="neutral",
            message=f"Nuclei found {len(parsed)} template match(es)",
            duration_ms=result.duration_ms,
            findings_count=len(parsed),
        )

    def scan_findings(self, domain: str) -> list[NormalizedFinding]:
        if not self.is_available():
            return [NormalizedFinding(
                check_code="nuclei.unavailable",
                category="security",
                severity=Severity.INFO,
                status=FindingStatus.NOT_APPLICABLE,
                title="Nuclei not available",
                recommendation="Install nuclei to enable template-based scanning.",
            )]

        try:
            target_info = validate_target(f"https://{domain}")
        except TargetValidationError as exc:
            return [NormalizedFinding(
                check_code="nuclei.target_validation",
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
                check_code="nuclei.timeout",
                category="security",
                severity=Severity.INFO,
                status=FindingStatus.UNKNOWN,
                title=f"Nuclei timed out after {self.timeout}s",
                duration_ms=result.duration_ms,
            )]

        parsed = parse_nuclei_jsonl(result.stdout)
        return self.normalize(parsed)

    def build_command(self, target: str, options: dict | None = None) -> list[str]:
        cfg = getattr(settings, "SCANNER_CONFIG", {}).get("nuclei", {})
        tags = cfg.get("tags", ["cve", "exposure", "misconfig"])
        return [
            "nuclei",
            "-u", target,
            "-json",
            "-silent",
            "-timeout", "10",
            "-bulk-size", "25",
            "-concurrency", "10",
            "-rate-limit", "150",
            "-tags", ",".join(tags) if isinstance(tags, list) else tags,
        ]

    def parse(self, output: str) -> list[dict[str, Any]]:
        return parse_nuclei_jsonl(output)

    def normalize(self, parsed_results: list[dict[str, Any]]) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        for item in parsed_results:
            sev_raw = item.get("severity", "info").lower()
            severity = _NUCLEI_SEVERITY_MAP.get(sev_raw, Severity.MEDIUM)
            status = FindingStatus.FAIL if sev_raw not in ("info",) else FindingStatus.WARNING

            refs = item.get("reference", [])
            ref_url = refs[0] if refs else ""

            findings.append(NormalizedFinding(
                check_code=f"nuclei.{item.get('template_id', 'unknown')}",
                category="security",
                severity=severity,
                status=status,
                title=item.get("name", "Nuclei template match"),
                description=item.get("description", ""),
                evidence={
                    "matched_at": item.get("matched_at", ""),
                    "matcher_name": item.get("matcher_name", ""),
                    "extracted_results": item.get("extracted_results", []),
                    "tags": item.get("tags", []),
                },
                recommendation="Review the template documentation and apply the suggested fix.",
                reference_url=ref_url if isinstance(ref_url, str) else "",
            ))
        return findings


nuclei_scanner = NucleiScanner()
