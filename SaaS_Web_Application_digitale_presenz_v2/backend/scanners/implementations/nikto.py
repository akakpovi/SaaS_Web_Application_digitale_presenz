"""Nikto web vulnerability scanner adapter.

Completeness
------------
Nikto exits 0 even when it stops early because its own ``-maxtime`` expired, so
the exit code alone cannot prove coverage.  The adapter therefore also scans the
report for Nikto's "maximum execution time reached" diagnostic and reports the
run as incomplete in that case.  A partial Nikto report is still stored and
parsed (the operator sees what was found), but it never proves that the rest is
absent.
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
from scanners.parsers.nikto import parse_nikto_json, parse_nikto_text

logger = logging.getLogger(__name__)

#: Printed by Nikto when ``-maxtime`` cut the scan short (it still exits 0).
_MAXTIME_MARKERS = (
    "maximum execution time",
    "maximum run time",
)


class NiktoScanner(BaseScanner):
    """Nikto web vulnerability scanner adapter."""

    name = "nikto"
    scanner_type = ScannerType.CLI
    _binary = "nikto"

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("nikto", {}).get("timeout", 100)

    def execute(
        self,
        domain: str,
        context: ScanContext | None = None,
    ) -> ScanOutcome:
        """Run Nikto exactly once and return result + normalized findings."""
        if not self.is_available():
            return build_outcome(
                self,
                run=ToolRun(exit_code=-1),
                findings=[
                    NormalizedFinding(
                        check_code="nikto.unavailable",
                        category="security",
                        severity=Severity.INFO,
                        status=FindingStatus.NOT_APPLICABLE,
                        title="Nikto not available",
                        recommendation="Install nikto to enable web vulnerability scanning.",
                    )
                ],
                message="Nikto not available — skipped",
                status="neutral",
                recommendation="Install nikto to enable web vulnerability scanning.",
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
                self.build_command(target_info.hostname),
                context=context,
            )
        except SandboxError as exc:
            logger.error("Nikto sandbox unavailable: %s", exc)
            return unavailable_outcome(self, reason=str(exc))

        complete, reason = evaluate_completeness(run, ok_exit_codes=(0,))
        if complete and self._maxtime_reached(run):
            complete, reason = False, "maxtime_reached"
        if complete and not self._looks_like_nikto_report(run.stdout):
            complete, reason = False, "unparsable_report"

        parsed = parse_nikto_json(run.stdout) or parse_nikto_text(run.stdout)
        findings = self.normalize(parsed)

        return build_outcome(
            self,
            run=run,
            findings=findings,
            message=(
                f"Nikto found {len(parsed)} issue(s)"
                if complete
                else f"Nikto scan incomplete ({reason}): "
                f"{len(parsed)} issue(s) seen so far"
            ),
            status="neutral" if complete else "warning",
            scan_complete=complete,
            partial_reason=reason,
            findings_count=len(parsed),
            raw_report=run.stdout or None,
            raw_report_format="nikto-text",
            raw_report_meta={"findings_count": len(parsed)},
        )

    @staticmethod
    def _maxtime_reached(run: ToolRun) -> bool:
        text = f"{run.stdout}\n{run.stderr}"
        return any(marker in text for marker in _MAXTIME_MARKERS)

    @staticmethod
    def _looks_like_nikto_report(output: str) -> bool:
        """A complete Nikto run writes its JSON report or its text findings."""
        import json as _json

        text = output or ""
        try:
            data = _json.loads(text)
        except (TypeError, ValueError):
            data = None
        if isinstance(data, dict) and "vulnerabilities" in data:
            return True
        # Text format: at least one finding or summary line.
        return any(line.strip().startswith("+") for line in text.splitlines())

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
        # Nikto must finish before the sandbox kills the container: -maxtime is
        # its own per-host budget, kept below the sandbox timeout so the report
        # is closed and the partial result is still usable.
        #
        # No -Format/-output: the sandbox root filesystem is read-only, so a
        # report *file* would fail to be written.  Nikto's default screen report
        # goes to stdout, which is collected by the runner.
        maxtime = max(5, int(self.timeout * 0.85))
        return [
            "nikto",
            "-h", target,
            "-nointeractive",
            "-ask", "no",
            "-timeout", "10",
            "-maxtime", f"{maxtime}s",
        ]

    def parse(self, output: str) -> list[dict[str, Any]]:
        return parse_nikto_json(output) or parse_nikto_text(output)

    def normalize(self, parsed_results: list[dict[str, Any]]) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        for item in parsed_results:
            msg = item.get("msg", "")
            osvdb = item.get("osvdb", "")
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
