"""testssl.sh TLS/SSL scanner adapter."""

from __future__ import annotations

import logging
import os
import shutil
from typing import Any

from django.conf import settings

from scanners.base import BaseScanner, NormalizedFinding, Severity, FindingStatus, ScanResult, ScannerType
from scanners.executors.command import default_executor
from scanners.exceptions import TargetValidationError
from scanners.parsers.testssl import parse_testssl_json
from scanners.security.target_validator import validate_target

logger = logging.getLogger(__name__)


class TestSSLScanner(BaseScanner):
    """testssl.sh TLS/SSL configuration scanner adapter."""

    name = "testssl"
    scanner_type = ScannerType.CLI
    _binary = "testssl"

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("testssl", {}).get("timeout", 60)

    def is_available(self) -> bool:
        return (
            shutil.which("testssl") is not None
            or shutil.which("testssl.sh") is not None
        )

    def _get_binary(self) -> str:
        return "testssl" if shutil.which("testssl") else "testssl.sh"

    def scan(self, domain: str) -> ScanResult:
        if not self.is_available():
            return self._create_result(
                score=None,
                status="neutral",
                message="testssl.sh not available — skipped",
                recommendation="Install testssl.sh for deep TLS analysis.",
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

        parsed = parse_testssl_json(result.stdout)
        high_sev = [p for p in parsed if p.get("severity") in ("high", "critical")]

        return self._create_result(
            score=None,
            status="critical" if high_sev else "neutral",
            message=f"testssl.sh found {len(parsed)} check(s), {len(high_sev)} high/critical",
            duration_ms=result.duration_ms,
            total_checks=len(parsed),
            high_severity_count=len(high_sev),
        )

    def scan_findings(self, domain: str) -> list[NormalizedFinding]:
        if not self.is_available():
            return [NormalizedFinding(
                check_code="testssl.unavailable",
                category="ssl",
                severity=Severity.INFO,
                status=FindingStatus.NOT_APPLICABLE,
                title="testssl.sh not available",
                recommendation="Install testssl.sh for comprehensive TLS analysis.",
            )]

        try:
            target_info = validate_target(f"https://{domain}")
        except TargetValidationError as exc:
            return [NormalizedFinding(
                check_code="testssl.target_validation",
                category="ssl",
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
                check_code="testssl.timeout",
                category="ssl",
                severity=Severity.INFO,
                status=FindingStatus.UNKNOWN,
                title=f"testssl.sh timed out after {self.timeout}s",
                duration_ms=result.duration_ms,
            )]

        parsed = parse_testssl_json(result.stdout)
        return self.normalize(parsed)

    def build_command(self, target: str, options: dict | None = None) -> list[str]:
        return [
            self._get_binary(),
            "--jsonfile", "/dev/stdout",
            "--quiet",
            "--nodns", "min",
            "--color", "0",
            "--parallel",
            "--", f"{target}:443",
        ]

    def parse(self, output: str) -> list[dict[str, Any]]:
        return parse_testssl_json(output)

    def normalize(self, parsed_results: list[dict[str, Any]]) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        severity_map = {
            "info": (Severity.INFO, FindingStatus.PASS),
            "low": (Severity.LOW, FindingStatus.WARNING),
            "medium": (Severity.MEDIUM, FindingStatus.WARNING),
            "high": (Severity.HIGH, FindingStatus.FAIL),
            "critical": (Severity.CRITICAL, FindingStatus.FAIL),
        }

        for item in parsed_results:
            sev_raw = item.get("severity", "info").lower()
            severity, status = severity_map.get(sev_raw, (Severity.INFO, FindingStatus.PASS))
            check_id = item.get("id", "unknown")

            cve = item.get("cve", "")
            ref = f"https://cve.mitre.org/cgi-bin/cvename.cgi?name={cve}" if cve else ""

            findings.append(NormalizedFinding(
                check_code=f"testssl.{check_id}",
                category="ssl",
                severity=severity,
                status=status,
                title=f"TLS check: {check_id}",
                description=item.get("finding", ""),
                evidence=item,
                reference_url=ref,
            ))

        return findings


testssl_scanner = TestSSLScanner()
