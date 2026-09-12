"""WhatWeb technology detection adapter."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from scanners.base import BaseScanner, NormalizedFinding, Severity, FindingStatus, ScanResult, ScannerType
from scanners.executors.command import default_executor
from scanners.exceptions import TargetValidationError
from scanners.parsers.whatweb import parse_whatweb_json
from scanners.security.target_validator import validate_target

logger = logging.getLogger(__name__)

# Technologies that indicate potential version disclosure risk
_SENSITIVE_TECH = frozenset({
    "PHP", "WordPress", "Drupal", "Joomla", "Laravel",
    "Django", "Ruby-on-Rails", "ASP.NET", "jQuery",
    "Bootstrap",
})


class WhatWebScanner(BaseScanner):
    """WhatWeb technology fingerprinting adapter."""

    name = "whatweb"
    scanner_type = ScannerType.CLI
    _binary = "whatweb"

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("whatweb", {}).get("timeout", 30)

    def scan(self, domain: str) -> ScanResult:
        if not self.is_available():
            return self._create_result(
                score=None,
                status="neutral",
                message="WhatWeb not available — skipped",
                recommendation="Install whatweb to enable technology detection.",
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

        parsed = parse_whatweb_json(result.stdout)
        techs = [p.get("technology", "") for p in parsed]

        return self._create_result(
            score=None,
            status="neutral",
            message=f"Detected {len(techs)} technologies: {', '.join(techs[:5])}",
            duration_ms=result.duration_ms,
            technologies=techs,
        )

    def scan_findings(self, domain: str) -> list[NormalizedFinding]:
        if not self.is_available():
            return [NormalizedFinding(
                check_code="whatweb.unavailable",
                category="security",
                severity=Severity.INFO,
                status=FindingStatus.NOT_APPLICABLE,
                title="WhatWeb not available",
                recommendation="Install whatweb to enable technology detection.",
            )]

        try:
            target_info = validate_target(f"https://{domain}")
        except TargetValidationError as exc:
            return [NormalizedFinding(
                check_code="whatweb.target_validation",
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
                check_code="whatweb.timeout",
                category="security",
                severity=Severity.INFO,
                status=FindingStatus.UNKNOWN,
                title=f"WhatWeb timed out after {self.timeout}s",
                duration_ms=result.duration_ms,
            )]

        parsed = parse_whatweb_json(result.stdout)
        return self.normalize(parsed)

    def build_command(self, target: str, options: dict | None = None) -> list[str]:
        return [
            "whatweb",
            "--log-json", "/dev/stdout",
            "--color", "never",
            "--no-errors",
            "--quiet",
            "--aggression", "1",  # Passive/stealthy
            "--", target,
        ]

    def parse(self, output: str) -> list[dict[str, Any]]:
        return parse_whatweb_json(output)

    def normalize(self, parsed_results: list[dict[str, Any]]) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        all_techs = [p.get("technology", "") for p in parsed_results]

        for item in parsed_results:
            tech = item.get("technology", "")
            versions = item.get("versions", [])
            severity = Severity.LOW if tech in _SENSITIVE_TECH else Severity.INFO
            status = FindingStatus.WARNING if (tech in _SENSITIVE_TECH and versions) else FindingStatus.PASS

            findings.append(NormalizedFinding(
                check_code=f"whatweb.technology.{tech.lower().replace(' ', '_').replace('-', '_')}",
                category="security",
                severity=severity,
                status=status,
                title=f"Technology detected: {tech}" + (f" {', '.join(versions)}" if versions else ""),
                description=(
                    f"Version information exposed for {tech}" if versions and tech in _SENSITIVE_TECH
                    else f"{tech} detected"
                ),
                evidence=item,
                recommendation=(
                    f"Consider hiding or obfuscating {tech} version information."
                    if versions and tech in _SENSITIVE_TECH else ""
                ),
            ))

        # Summary finding
        findings.append(NormalizedFinding(
            check_code="whatweb.technologies_summary",
            category="security",
            severity=Severity.INFO,
            status=FindingStatus.PASS,
            title=f"WhatWeb detected {len(all_techs)} technologies",
            evidence={"technologies": all_techs},
        ))

        return findings


whatweb_scanner = WhatWebScanner()
