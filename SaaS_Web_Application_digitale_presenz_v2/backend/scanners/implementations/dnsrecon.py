"""dnsrecon DNS reconnaissance adapter.

Scope
-----
Only the non-intrusive ``std`` enumeration (NS/SOA/A/AAAA/MX/SRV/PTR) runs in
the sandbox: no zone transfer, no dictionary brute force, no reverse sweep on
address space the operator does not own.  ``--lifetime`` keeps every individual
query short so the whole enumeration fits the per-step budget.

Completeness
------------
``std`` enumeration is a point-in-time query of public DNS.  A truncated report
or a sandbox-killed run is reported as incomplete, and an empty result set is
only meaningful when the run was explicitly complete.
"""

from __future__ import annotations

import json
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

#: dnsrecon JSON entries that describe the run instead of a DNS record.
_NON_RECORD_TYPES = frozenset({"SCANINFO"})

logger = logging.getLogger(__name__)


def _has_json_document(output: str) -> bool:
    """True when the buffer carries at least one JSON document."""
    if not output or not output.strip():
        return False
    decoder = json.JSONDecoder()
    for index, char in enumerate(output):
        if char not in "[{":
            continue
        try:
            decoder.raw_decode(output[index:])
        except ValueError:
            continue
        return True
    return False


def _parse_dnsrecon_json(output: str) -> list[dict[str, Any]]:
    """Parse dnsrecon JSON output.

    dnsrecon writes the JSON report (``-j /dev/stdout``) and its human-readable
    progress to the *same* stream, so the document is located inside a mixed
    buffer rather than being the whole buffer.  ``raw_decode`` is used from each
    candidate start so trailing progress lines are ignored instead of making the
    whole report unparsable.
    """
    if not output or not output.strip():
        return []

    decoder = json.JSONDecoder()
    for index, char in enumerate(output):
        if char not in "[{":
            continue
        try:
            data, _end = decoder.raw_decode(output[index:])
        except ValueError:
            continue
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            results = data.get("results")
            if isinstance(results, list):
                return [item for item in results if isinstance(item, dict)]
            return [data]
    return []


class DnsreconScanner(BaseScanner):
    """dnsrecon DNS reconnaissance adapter."""

    name = "dnsrecon"
    scanner_type = ScannerType.CLI
    _binary = "dnsrecon"

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("dnsrecon", {}).get("timeout", 30)

    def execute(
        self,
        domain: str,
        context: ScanContext | None = None,
    ) -> ScanOutcome:
        """Run dnsrecon exactly once and return result + normalized findings."""
        if not self.is_available():
            return build_outcome(
                self,
                run=ToolRun(exit_code=-1),
                findings=[
                    NormalizedFinding(
                        check_code="dnsrecon.unavailable",
                        category="dns",
                        severity=Severity.INFO,
                        status=FindingStatus.NOT_APPLICABLE,
                        title="dnsrecon not available",
                        recommendation="Install dnsrecon for DNS reconnaissance.",
                    )
                ],
                message="dnsrecon not available — skipped",
                status="neutral",
                recommendation="Install dnsrecon for comprehensive DNS reconnaissance.",
                scan_complete=False,
                partial_reason="unavailable",
            )

        try:
            target_info = resolve_target(domain, context, domain_only=True)
            dns_name = getattr(target_info, "hostname", None) or str(target_info)
        except TargetValidationError as exc:
            return target_validation_outcome(self, error=str(exc), category="dns")

        try:
            run = run_tool(
                self,
                self.build_command(dns_name),
                context=context,
            )
        except SandboxError as exc:
            logger.error("dnsrecon sandbox unavailable: %s", exc)
            return unavailable_outcome(self, reason=str(exc))

        complete, reason = evaluate_completeness(run, ok_exit_codes=(0,))
        parsed = _parse_dnsrecon_json(run.stdout)
        if complete and parsed == [] and not _has_json_document(run.stdout or ""):
            # dnsrecon -j always writes a JSON document (an empty list when the
            # enumeration found nothing).  No document at all is not a report.
            complete, reason = False, "unparsable_report"
        findings = self.normalize(parsed)

        return build_outcome(
            self,
            run=run,
            findings=findings,
            message=(
                f"dnsrecon found {len(parsed)} DNS record(s)"
                if complete
                else f"dnsrecon scan incomplete ({reason}): "
                f"{len(parsed)} record(s) seen so far"
            ),
            status="neutral" if complete else "warning",
            scan_complete=complete,
            partial_reason=reason,
            record_count=len(parsed),
            raw_report=run.stdout or None,
            raw_report_format="dnsrecon-json",
            raw_report_meta={"records": len(parsed)},
        )

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
        cfg = getattr(settings, "SCANNER_CONFIG", {}).get("dnsrecon", {})
        lifetime = int(cfg.get("lifetime_seconds", 8) or 8)
        return [
            "dnsrecon",
            "-d", target,
            "-t", "std",           # standard enumeration only
            "-j", "/dev/stdout",   # JSON to stdout
            "--lifetime", str(lifetime),
        ]

    def parse(self, output: str) -> list[dict[str, Any]]:
        return _parse_dnsrecon_json(output)

    def normalize(self, parsed_results: list[dict[str, Any]]) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        record_types: dict[str, list[dict[str, Any]]] = {}
        for record in parsed_results:
            rtype = str(record.get("type", "")).upper()
            if not rtype or rtype in _NON_RECORD_TYPES:
                # dnsrecon's own run header ("ScanInfo": command line, start
                # time) is not a DNS record and must not become a finding.
                continue
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
