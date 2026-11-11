"""Feroxbuster recursive web content discovery adapter."""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

from scanners.base import (
    BaseScanner,
    NormalizedFinding,
    Severity,
    FindingStatus,
    ScanResult,
    ScannerType,
)
from scanners.executors.sandbox import get_sandbox_executor
from scanners.exceptions import TargetValidationError
from scanners.security.target_validator import validate_target

logger = logging.getLogger(__name__)


def _parse_feroxbuster_output(output: str) -> list[dict[str, Any]]:
    """Parse Feroxbuster NDJSON output (--json flag)."""
    findings: list[dict[str, Any]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            if item.get("type") == "response":
                findings.append(
                    {
                        "url": item.get("url", ""),
                        "status": item.get("status", 0),
                        "content_length": item.get("content_length", 0),
                        "word_count": item.get("word_count", 0),
                        "line_count": item.get("line_count", 0),
                    }
                )
        except json.JSONDecodeError:
            continue
    return findings


class FeroxbusterScanner(BaseScanner):
    """Feroxbuster recursive content discovery adapter."""

    name = "feroxbuster"
    scanner_type = ScannerType.CLI
    _binary = "feroxbuster"

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("feroxbuster", {}).get("timeout", 120)

    def scan(self, domain: str) -> ScanResult:
        if not self.is_available():
            return self._create_result(
                score=None,
                status="neutral",
                message="Feroxbuster not available — skipped",
            )

        try:
            target_info = validate_target(f"https://{domain}")
        except TargetValidationError as exc:
            return self._create_result(score=None, status="critical", message=str(exc))

        result = get_sandbox_executor().run(
            command=self.build_command(target_info.url),
            timeout=self.timeout,
            scanner_name=self.name,
        )

        parsed = _parse_feroxbuster_output(result.stdout)
        return self._create_result(
            score=None,
            status="neutral",
            message=f"Feroxbuster found {len(parsed)} URL(s)",
            duration_ms=result.duration_ms,
            urls_found=len(parsed),
        )

    def scan_findings(self, domain: str) -> list[NormalizedFinding]:
        if not self.is_available():
            return [
                NormalizedFinding(
                    check_code="feroxbuster.unavailable",
                    category="security",
                    severity=Severity.INFO,
                    status=FindingStatus.NOT_APPLICABLE,
                    title="Feroxbuster not available",
                )
            ]

        try:
            target_info = validate_target(f"https://{domain}")
        except TargetValidationError as exc:
            return [
                NormalizedFinding(
                    check_code="feroxbuster.target_validation",
                    category="security",
                    severity=Severity.HIGH,
                    status=FindingStatus.FAIL,
                    title="Target validation failed",
                    description=str(exc),
                )
            ]

        result = get_sandbox_executor().run(
            command=self.build_command(target_info.url),
            timeout=self.timeout,
            scanner_name=self.name,
        )

        if result.timed_out:
            return [
                NormalizedFinding(
                    check_code="feroxbuster.timeout",
                    category="security",
                    severity=Severity.INFO,
                    status=FindingStatus.UNKNOWN,
                    title=f"Feroxbuster timed out after {self.timeout}s",
                    duration_ms=result.duration_ms,
                )
            ]

        parsed = _parse_feroxbuster_output(result.stdout)
        return self.normalize(parsed)

    def build_command(self, target: str, options: dict | None = None) -> list[str]:
        cfg = getattr(settings, "SCANNER_CONFIG", {}).get("feroxbuster", {})
        wordlist = cfg.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        threads = cfg.get("threads", 10)
        return [
            "feroxbuster",
            "--url",
            target,
            "--wordlist",
            wordlist,
            "--threads",
            str(threads),
            "--json",
            "--quiet",
            "--no-recursion",  # Keep it fast / non-intrusive
            "--timeout",
            "10",
            "--rate-limit",
            "50",
        ]

    def parse(self, output: str) -> list[dict[str, Any]]:
        return _parse_feroxbuster_output(output)

    def normalize(
        self, parsed_results: list[dict[str, Any]]
    ) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        sensitive_patterns = {"admin", "backup", "config", ".env", ".git", "wp-admin"}

        for item in parsed_results:
            url = item.get("url", "")
            lower_url = url.lower()
            is_sensitive = any(p in lower_url for p in sensitive_patterns)
            severity = Severity.HIGH if is_sensitive else Severity.LOW
            status = FindingStatus.FAIL if is_sensitive else FindingStatus.WARNING

            findings.append(
                NormalizedFinding(
                    check_code=f"feroxbuster.url.{abs(hash(url)) % 100000}",
                    category="security",
                    severity=severity,
                    status=status,
                    title=f"URL found: {url[:200]}",
                    description=f"Feroxbuster discovered '{url}' (HTTP {item.get('status', '?')})",
                    evidence=item,
                    recommendation="Review access controls for this path."
                    if is_sensitive
                    else "",
                )
            )

        return findings


feroxbuster_scanner = FeroxbusterScanner()
