"""Parsing of uploaded vulnerability reports (OWASP ZAP, Nuclei).

The scanner adapters in :mod:`scanners.parsers` already know each tool's wire
format; this module reuses them and adds the two things the ingestion pipeline
needs:

* deterministic **format detection** for an uploaded file, so a ZAP report is
  never handed to the Nuclei parser (a wrong guess could resolve findings);
* a bounded, uniform **mapping to ``SecurityFinding`` fields** (name,
  severity, description, proof).

Nothing here touches the database.  The payload is untrusted: names and proof
are trimmed, de-duplicated and truncated before they reach the model, and an
unrecognised document raises :class:`ReportParseError` instead of being read as
an empty report (which would silently resolve every open finding of the asset).

Proof text is raw evidence (HTTP responses, payloads).  It is stored on the
finding and bounded before ever being sent to the AI provider; it is never
logged here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from scanners.parsers.nuclei import parse_nuclei_jsonl
from scanners.parsers.zap import parse_zap_json

#: Hard limits applied to every upload, before and after parsing.
MAX_REPORT_BYTES = 5 * 1024 * 1024
MAX_FINDINGS_PER_REPORT = 2_000
MAX_NAME_CHARS = 255
MAX_DESCRIPTION_CHARS = 4_000
MAX_PROOF_CHARS = 4_000
MAX_PROOF_ENTRIES = 5

ZAP = "zap"
NUCLEI = "nuclei"
SUPPORTED_SOURCES = (ZAP, NUCLEI)

#: Canonical ``SecurityFinding.Severity`` values.
SEVERITIES = ("critical", "high", "medium", "low", "info")

_SEVERITY_ALIASES = {
    "informational": "info",
    "information": "info",
    "unknown": "info",
    "none": "info",
    "warning": "medium",
    "moderate": "medium",
    "severe": "high",
}

_SEVERITY_RANK = {severity: rank for rank, severity in enumerate(SEVERITIES)}


class ReportParseError(Exception):
    """An uploaded report that cannot be ingested safely.

    ``code`` is a stable, non-sensitive identifier the HTTP layer returns; the
    detail is operator-facing French/English prose that never echoes file
    content.
    """

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ParsedFinding:
    """One vulnerability, already shaped like a ``SecurityFinding`` row."""

    vulnerability_name: str
    severity: str
    description: str = ""
    proof_or_payload: str = ""


@dataclass(frozen=True)
class ParsedReport:
    """The result of parsing one uploaded file."""

    source: str
    findings: tuple[ParsedFinding, ...]
    skipped: int = 0

    @property
    def names(self) -> set[str]:
        return {finding.vulnerability_name for finding in self.findings}


def normalise_severity(value: Any) -> str:
    """Map any tool severity label to a ``SecurityFinding`` severity."""
    label = str(value or "").strip().lower()
    if label in SEVERITIES:
        return label
    return _SEVERITY_ALIASES.get(label, "info")


def _clean_name(value: Any, fallback: str) -> str:
    name = " ".join(str(value or "").split())
    if not name:
        name = fallback
    return name[:MAX_NAME_CHARS]


def _bounded(text: Any, limit: int) -> str:
    cleaned = str(text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(limit - 1, 0)] + "…"


def _join_proof(entries: Iterable[str]) -> str:
    seen: list[str] = []
    for entry in entries:
        value = str(entry or "").strip()
        if value and value not in seen:
            seen.append(value)
        if len(seen) >= MAX_PROOF_ENTRIES:
            break
    return _bounded("\n".join(seen), MAX_PROOF_CHARS)


def _document_shape(text: str) -> str | None:
    """Return ``"zap"`` / ``"nuclei"`` when the document looks like one.

    Only structural markers are inspected (never the alert content), so a
    valid report with zero findings is still recognised while a random JSON
    file is not.
    """
    stripped = text.strip()
    if not stripped:
        return None

    # Nuclei writes one JSON object per line.
    if stripped.startswith("{"):
        try:
            document = json.loads(stripped)
        except json.JSONDecodeError:
            document = None
        if isinstance(document, dict):
            if "site" in document or "alerts" in document:
                return ZAP
            if _is_nuclei_object(document):
                return NUCLEI
        if isinstance(document, list):
            return _list_shape(document)
        if document is None:
            return _jsonl_shape(stripped)
        return None

    if stripped.startswith("["):
        try:
            document = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        if isinstance(document, list):
            return _list_shape(document)
        return None

    return _jsonl_shape(stripped)


def _is_nuclei_object(document: dict[str, Any]) -> bool:
    return (
        "template-id" in document
        or "template_id" in document
        or (
            isinstance(document.get("info"), dict)
            and ("matched-at" in document or "matched_at" in document)
        )
    )


def _is_zap_alert(document: dict[str, Any]) -> bool:
    return (
        "pluginid" in document
        or "alert" in document
        or ("riskcode" in document and "name" in document)
    )


def _list_shape(document: list[Any]) -> str | None:
    for entry in document:
        if not isinstance(entry, dict):
            continue
        if _is_nuclei_object(entry):
            return NUCLEI
        if _is_zap_alert(entry):
            return ZAP
    return None


def _jsonl_shape(text: str) -> str | None:
    checked = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        checked += 1
        if checked > 5:
            break
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return None
        if isinstance(entry, dict):
            if _is_nuclei_object(entry):
                return NUCLEI
            if "site" in entry or "alerts" in entry:
                return ZAP
    return None


def detect_source(text: str) -> str | None:
    """Detect the report format without parsing it into findings."""
    return _document_shape(text)


def parse_report(text: str, *, source: str | None = None) -> ParsedReport:
    """Parse an uploaded report into ``SecurityFinding``-shaped findings.

    ``source`` pins the format (an explicit ``source`` form field); otherwise
    it is detected.  A document that does not match the expected format raises
    :class:`ReportParseError`: an unknown upload must never be treated as an
    empty report, because that would resolve every open finding of the asset.
    """
    if not text or not text.strip():
        raise ReportParseError("empty_report", "The uploaded report is empty.")
    if len(text) > MAX_REPORT_BYTES:
        raise ReportParseError("report_too_large", "The uploaded report is too large.")

    detected = _document_shape(text)
    if source:
        requested = str(source).strip().lower()
        if requested not in SUPPORTED_SOURCES:
            raise ReportParseError(
                "unsupported_source",
                f"Unsupported report source; expected one of {', '.join(SUPPORTED_SOURCES)}.",
            )
        if detected is not None and detected != requested:
            raise ReportParseError(
                "report_format_mismatch",
                f"The uploaded file does not look like a {requested.upper()} report.",
            )
        resolved = requested
    else:
        if detected is None:
            raise ReportParseError(
                "unknown_report_format",
                "The uploaded file is neither an OWASP ZAP report nor a Nuclei report.",
            )
        resolved = detected

    raw = (
        parse_zap_json(text)
        if resolved == ZAP
        else parse_nuclei_jsonl(_nuclei_lines(text))
    )
    mapped = (
        [_zap_finding(entry) for entry in raw]
        if resolved == ZAP
        else [_nuclei_finding(entry) for entry in raw]
    )

    findings, skipped = _dedupe(mapped)
    if len(findings) > MAX_FINDINGS_PER_REPORT:
        raise ReportParseError(
            "report_too_large",
            f"The report contains more than {MAX_FINDINGS_PER_REPORT} findings.",
        )

    return ParsedReport(source=resolved, findings=tuple(findings), skipped=skipped)


def _nuclei_lines(text: str) -> str:
    """Normalise a Nuclei JSON array to the JSONL the adapter expects."""
    stripped = text.strip()
    if not stripped.startswith("["):
        return text
    try:
        document = json.loads(stripped)
    except json.JSONDecodeError:
        return text
    if not isinstance(document, list):
        return text
    return "\n".join(json.dumps(entry) for entry in document if isinstance(entry, dict))


def _zap_finding(alert: dict[str, Any]) -> ParsedFinding:
    alert_id = str(alert.get("alert_id", "") or "")
    name = _clean_name(
        alert.get("name"),
        f"ZAP alert {alert_id}" if alert_id else "ZAP alert",
    )

    description = _bounded(alert.get("description"), MAX_DESCRIPTION_CHARS)
    solution = _bounded(alert.get("solution"), 1_200)
    if solution:
        description = _bounded(
            f"{description}\n\nSolution: {solution}".strip(),
            MAX_DESCRIPTION_CHARS,
        )

    entries: list[str] = []
    instances = alert.get("instances")
    if isinstance(instances, list):
        for instance in instances[:MAX_PROOF_ENTRIES]:
            if not isinstance(instance, dict):
                continue
            line = " ".join(
                part
                for part in (
                    str(instance.get("method", "") or "").strip(),
                    str(instance.get("uri", "") or "").strip(),
                )
                if part
            )
            if line:
                entries.append(line)
            evidence = _bounded(instance.get("evidence"), 400)
            if evidence:
                entries.append(f"evidence: {evidence}")
            parameter = str(instance.get("param", "") or "").strip()
            if parameter:
                entries.append(f"parameter: {parameter}")
            attack = _bounded(instance.get("attack"), 400)
            if attack:
                entries.append(f"attack: {attack}")

    if not entries:
        reference = str(alert.get("reference", "") or "").strip()
        if reference:
            entries.append(reference)

    meta = []
    if alert_id:
        meta.append(f"plugin: {alert_id}")
    cwe = str(alert.get("cweid", "") or "").strip()
    if cwe and cwe != "0":
        meta.append(f"CWE-{cwe}")
    confidence = str(alert.get("confidence", "") or "").strip()
    if confidence:
        meta.append(f"confidence: {confidence}")
    if meta:
        entries.insert(0, " · ".join(meta))

    return ParsedFinding(
        vulnerability_name=name,
        severity=normalise_severity(alert.get("severity")),
        description=description,
        proof_or_payload=_join_proof(entries),
    )


def _nuclei_finding(match: dict[str, Any]) -> ParsedFinding:
    template_id = str(match.get("template_id", "") or "").strip()
    name = _clean_name(
        match.get("name"),
        template_id or "Nuclei template match",
    )

    description = _bounded(match.get("description"), MAX_DESCRIPTION_CHARS)

    entries: list[str] = []
    if template_id:
        entries.append(f"template: {template_id}")
    matched_at = str(match.get("matched_at", "") or "").strip()
    if matched_at:
        entries.append(f"matched at: {matched_at}")
    matcher_name = str(match.get("matcher_name", "") or "").strip()
    if matcher_name:
        entries.append(f"matcher: {matcher_name}")
    extracted = match.get("extracted_results")
    if isinstance(extracted, list) and extracted:
        joined = _bounded(" | ".join(str(item) for item in extracted[:10]), 1_200)
        entries.append(f"extracted: {joined}")
    elif isinstance(extracted, str) and extracted.strip():
        entries.append(f"extracted: {_bounded(extracted, 1_200)}")
    curl = _bounded(match.get("curl_command"), 1_200)
    if curl:
        entries.append(f"curl: {curl}")

    return ParsedFinding(
        vulnerability_name=name,
        severity=normalise_severity(match.get("severity")),
        description=description,
        proof_or_payload=_join_proof(entries),
    )


def _dedupe(findings: list[ParsedFinding]) -> tuple[list[ParsedFinding], int]:
    """Collapse repeated names inside one report (ZAP repeats per URL).

    The strongest severity wins and the evidence is merged, so one uploaded
    report can never create two rows for the same vulnerability.
    """
    merged: dict[str, ParsedFinding] = {}
    skipped = 0
    for finding in findings:
        key = finding.vulnerability_name.casefold()
        current = merged.get(key)
        if current is None:
            merged[key] = finding
            continue
        skipped += 1
        severity = (
            current.severity
            if _SEVERITY_RANK[current.severity] <= _SEVERITY_RANK[finding.severity]
            else finding.severity
        )
        description = (
            current.description
            if len(current.description) >= len(finding.description)
            else finding.description
        )
        merged[key] = ParsedFinding(
            vulnerability_name=current.vulnerability_name,
            severity=severity,
            description=description,
            proof_or_payload=_join_proof(
                [current.proof_or_payload, finding.proof_or_payload]
            ),
        )
    return list(merged.values()), skipped
