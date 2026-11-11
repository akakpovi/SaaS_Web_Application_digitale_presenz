"""WhatWeb technology detection adapter.

Completeness
------------
WhatWeb writes one JSON object per scanned target.  An unreachable target
produces an empty log and a non-zero exit code, and the adapter reports that run
as incomplete: "nothing detected" and "nothing was scanned" are different
results and must not be confused.
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
from scanners.parsers.whatweb import parse_whatweb_json

logger = logging.getLogger(__name__)

# Technologies that indicate potential version disclosure risk
_SENSITIVE_TECH = frozenset(
    {
        "PHP",
        "WordPress",
        "Drupal",
        "Joomla",
        "Laravel",
        "Django",
        "Ruby-on-Rails",
        "ASP.NET",
        "jQuery",
        "Bootstrap",
    }
)


class WhatWebScanner(BaseScanner):
    """WhatWeb technology fingerprinting adapter."""

    name = "whatweb"
    scanner_type = ScannerType.CLI
    _binary = "whatweb"

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("whatweb", {}).get("timeout", 25)

    def execute(
        self,
        domain: str,
        context: ScanContext | None = None,
    ) -> ScanOutcome:
        """Run WhatWeb exactly once and return result + normalized findings."""
        if not self.is_available():
            return build_outcome(
                self,
                run=ToolRun(exit_code=-1),
                findings=[
                    NormalizedFinding(
                        check_code="whatweb.unavailable",
                        category="security",
                        severity=Severity.INFO,
                        status=FindingStatus.NOT_APPLICABLE,
                        title="WhatWeb not available",
                        recommendation="Install whatweb to enable technology detection.",
                    )
                ],
                message="WhatWeb not available — skipped",
                status="neutral",
                recommendation="Install whatweb to enable technology detection.",
                scan_complete=False,
                partial_reason="unavailable",
            )

        try:
            target_info = resolve_target(domain, context)
        except TargetValidationError as exc:
            return target_validation_outcome(self, error=str(exc))

        try:
            run = run_tool(
                self,
                self.build_command(target_info.url),
                context=context,
            )
        except SandboxError as exc:
            logger.error("WhatWeb sandbox unavailable: %s", exc)
            return unavailable_outcome(self, reason=str(exc))

        complete, reason = evaluate_completeness(run, ok_exit_codes=(0,))
        if complete and not self._looks_like_whatweb_json(run.stdout):
            # WhatWeb failed to reach the target: the log stays empty or holds
            # an error line, which is not a technology fingerprint.
            complete, reason = False, "unparsable_report"

        parsed = parse_whatweb_json(run.stdout)
        findings = self.normalize(parsed)
        techs = [p.get("technology", "") for p in parsed if p.get("technology")]

        return build_outcome(
            self,
            run=run,
            findings=findings,
            message=(
                f"Detected {len(techs)} technologies: {', '.join(techs[:5])}"
                if complete
                else f"WhatWeb scan incomplete ({reason}): "
                f"{len(techs)} technologies seen so far"
            ),
            status="neutral" if complete else "warning",
            scan_complete=complete,
            partial_reason=reason,
            technologies=techs,
            raw_report=run.stdout or None,
            raw_report_format="whatweb-json",
            raw_report_meta={
                "technologies": len(techs),
                "stderr_present": bool(run.stderr.strip()),
            },
        )

    @staticmethod
    def _looks_like_whatweb_json(output: str) -> bool:
        """WhatWeb --log-json writes JSON objects, one per target."""
        for line in (output or "").splitlines():
            line = line.strip()
            if line.startswith("{") or line.startswith("["):
                return True
        return False

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
        return [
            "whatweb",
            "--log-json",
            "/dev/stdout",
            "--color",
            "never",
            "--quiet",
            # Aggression 1 = passive: one request per target, no payloads.
            "--aggression",
            "1",
            "--",
            target,
        ]

    def parse(self, output: str) -> list[dict[str, Any]]:
        return parse_whatweb_json(output)

    def normalize(
        self, parsed_results: list[dict[str, Any]]
    ) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        all_techs = [p.get("technology", "") for p in parsed_results]

        for item in parsed_results:
            tech = item.get("technology", "")
            versions = item.get("versions", [])
            severity = Severity.LOW if tech in _SENSITIVE_TECH else Severity.INFO
            status = (
                FindingStatus.WARNING
                if (tech in _SENSITIVE_TECH and versions)
                else FindingStatus.PASS
            )

            findings.append(
                NormalizedFinding(
                    check_code=f"whatweb.technology.{tech.lower().replace(' ', '_').replace('-', '_')}",
                    category="security",
                    severity=severity,
                    status=status,
                    title=f"Technology detected: {tech}"
                    + (f" {', '.join(versions)}" if versions else ""),
                    description=(
                        f"Version information exposed for {tech}"
                        if versions and tech in _SENSITIVE_TECH
                        else f"{tech} detected"
                    ),
                    evidence=item,
                    recommendation=(
                        f"Consider hiding or obfuscating {tech} version information."
                        if versions and tech in _SENSITIVE_TECH
                        else ""
                    ),
                )
            )

        if all_techs:
            findings.append(
                NormalizedFinding(
                    check_code="whatweb.technologies_summary",
                    category="security",
                    severity=Severity.INFO,
                    status=FindingStatus.PASS,
                    title=f"WhatWeb detected {len(all_techs)} technologies",
                    evidence={"technologies": all_techs},
                )
            )

        return findings


whatweb_scanner = WhatWebScanner()
