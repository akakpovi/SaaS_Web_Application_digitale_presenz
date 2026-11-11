"""Automatic ingestion of security scanner results into ``SecurityFinding``.

The scan pipeline stores every scanner outcome twice: a ``scans.Finding`` (the
raw, per-scan normalised record used by scoring and reports) and, through this
module, a ``SecurityFinding`` (the long-lived, tenant-owned vulnerability the AI
advisor explains).  The second one is what makes the automated experience
*continuous*: the same vulnerability is recognised across scans, keeps its
history, and can be closed when a later scan no longer reports it.

Only the vulnerability scanners are ingested here.  Health checks (SSL, DNS,
headers, uptime, …) already have their own ``CheckResult``/``Finding`` model
and are not vulnerabilities in the ``SecurityFinding`` sense.

Completeness matters: a scan stopped by its timeout still produces the findings
it managed to collect, but it did **not** prove that the others are gone, so
``complete=False`` disables resolution.  Ingesting a partial report must never
close an open finding.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from advisory.parsers import (
    MAX_DESCRIPTION_CHARS,
    MAX_NAME_CHARS,
    MAX_PROOF_CHARS,
    NUCLEI,
    ZAP,
    ParsedFinding,
    ParsedReport,
)
from advisory.services.ingestion import IngestOutcome, ingest_report

logger = logging.getLogger("advisory.scan_ingestion")

#: Scanners whose output is a vulnerability report rather than a health check.
SECURITY_SCANNERS: tuple[str, ...] = (ZAP, NUCLEI)

#: Check codes the adapters use when the *tool itself* could not run.
#: Such a "finding" is not a vulnerability: the scan produced no evidence at
#: all, so its absence of other findings proves nothing.  Ingesting it would
#: create a phantom finding and resolve every real one — the exact failure the
#: ingestion pipeline must never have.
_EXECUTION_FAILURE_SUFFIXES = (
    ".sandbox_unavailable",
    ".unavailable",
    ".disabled",
    ".timeout",
    ".memory_exceeded",
    ".target_validation",
    ".blocked",
    # Nuclei now reports an incomplete run explicitly.  These findings are
    # operational diagnostics, never vulnerabilities: they must not create a
    # SecurityFinding, and their presence forces a non-resolving ingest.
    ".host_unresponsive",
    ".incomplete",
    ".output_truncated",
    ".execution_failed",
)

_MAX_EVIDENCE_CHARS = 1_500


def _bounded(value: Any, limit: int) -> str:
    text = "" if value is None else str(value).strip()
    if len(text) <= limit:
        return text
    return f"{text[: max(limit - 1, 0)]}…"


def _bounded_json(value: Any, limit: int = _MAX_EVIDENCE_CHARS) -> str:
    try:
        dumped = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        dumped = str(value)
    return _bounded(dumped, limit)


def _proof_for(finding: Any) -> str:
    """Render the scanner evidence as bounded text.

    The evidence dictionary is untrusted scanner output; it is stored as proof
    for the operator and is truncated before it ever reaches the AI provider.
    """
    lines: list[str] = []
    check_code = getattr(finding, "check_code", "") or ""
    if check_code:
        lines.append(f"check: {check_code}")

    evidence = getattr(finding, "evidence", None)
    if evidence:
        lines.append(f"evidence: {_bounded_json(evidence)}")

    for label, value in (
        ("detected", getattr(finding, "detected_value", None)),
        ("expected", getattr(finding, "expected_value", None)),
    ):
        if value not in (None, "", [], {}):
            lines.append(f"{label}: {_bounded_json(value, 400)}")

    reference = getattr(finding, "reference_url", "") or ""
    if reference:
        lines.append(f"reference: {_bounded(reference, 300)}")

    return _bounded("\n".join(lines), MAX_PROOF_CHARS)


def parsed_report_for(
    scanner_name: str,
    findings: Iterable[Any],
) -> ParsedReport:
    """Convert the scanner's normalised findings into a ``ParsedReport``.

    Identical names inside one run are collapsed (last description wins, proof
    merged) so a scan that reports the same template on several URLs can never
    create two rows for the same vulnerability.
    """
    merged: dict[str, ParsedFinding] = {}
    for finding in findings:
        name = _bounded(getattr(finding, "title", "") or "", MAX_NAME_CHARS)
        if not name.strip():
            code = getattr(finding, "check_code", "") or "unknown"
            name = f"Finding {code}"[:MAX_NAME_CHARS]

        description = _bounded(
            getattr(finding, "description", "") or "", MAX_DESCRIPTION_CHARS
        )
        recommendation = _bounded(getattr(finding, "recommendation", "") or "", 800)
        if recommendation:
            description = _bounded(
                f"{description}\n\nRecommendation: {recommendation}".strip(),
                MAX_DESCRIPTION_CHARS,
            )

        proof = _proof_for(finding)
        severity = str(getattr(finding, "severity", "") or "").strip().lower()
        if severity not in ("critical", "high", "medium", "low", "info"):
            severity = "info"

        key = name.casefold()
        current = merged.get(key)
        if current is not None:
            proof = _bounded(
                f"{current.proof_or_payload}\n{proof}".strip(), MAX_PROOF_CHARS
            )
        merged[key] = ParsedFinding(
            vulnerability_name=name,
            severity=severity,
            description=description,
            proof_or_payload=proof,
        )

    return ParsedReport(source=scanner_name, findings=tuple(merged.values()))


def _is_execution_meta(finding: Any) -> bool:
    """True for the operational findings adapters emit when a tool did not
    produce a usable report (timeout, sandbox error, host drop, …)."""
    code = str(getattr(finding, "check_code", "") or "").strip().lower()
    return bool(code) and code.endswith(_EXECUTION_FAILURE_SUFFIXES)


def execution_failed(findings: Iterable[Any]) -> bool:
    """True when the run reports that the tool could not actually scan."""
    return any(_is_execution_meta(finding) for finding in findings)


def ingest_scan_findings(
    *,
    scan: Any,
    scanner_name: str,
    findings: Iterable[Any],
    complete: bool = True,
    now=None,
) -> IngestOutcome | None:
    """Persist one security scanner's results; returns ``None`` when skipped.

    Skips (never raises) for anything that is not a usable tenant-owned
    security scanner run: guest scans, organization-less legacy websites, the
    health scanners, and runs where the tool itself failed to execute (the
    adapter then emits a ``*.sandbox_unavailable`` style finding instead of a
    report).  Database errors are left to the caller, which logs them without
    failing the scan.
    """
    if scanner_name not in SECURITY_SCANNERS:
        return None

    website = getattr(scan, "website", None)
    if website is None or getattr(website, "is_guest", False):
        return None
    organization_id = getattr(website, "organization_id", None)
    if organization_id is None:
        return None

    findings = list(findings)
    meta = [finding for finding in findings if _is_execution_meta(finding)]
    real_findings = [finding for finding in findings if not _is_execution_meta(finding)]

    if meta and not real_findings:
        logger.warning(
            "security_ingestion_skipped scanner=%s scan=%s reason=tool_not_executed",
            scanner_name,
            getattr(scan, "pk", None),
        )
        return None

    if meta:
        # The adapter managed to collect partial output before the failure:
        # ingest what it found, but never resolve a missing finding.
        complete = False
        logger.info(
            "security_ingestion_partial scanner=%s scan=%s findings=%d",
            scanner_name,
            getattr(scan, "pk", None),
            len(real_findings),
        )

    report = parsed_report_for(scanner_name, real_findings)
    return ingest_report(
        website.organization,
        website,
        report,
        now=now,
        resolve_missing=complete,
    )
