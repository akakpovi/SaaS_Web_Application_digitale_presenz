"""testssl.sh JSON output parser.

``testssl --jsonfile-pretty`` nests every check inside per-engine sections
(``scanResult`` → ``pretest``/``ciphers``/``vulnerabilities``/… → list of
checks), while flat fixtures and older versions use a plain array of checks.
Both shapes are accepted: the parser walks the document and keeps every object
carrying an ``id`` and a ``severity``.  Without that walk the section objects
themselves were returned, which produced findings with an empty id
(``testssl.`` / "TLS check: ") and hid every real TLS result.
"""

from __future__ import annotations

import json
from typing import Any, Iterator

_SEVERITY_MAP = {
    "INFO": "info",
    "OK": "info",
    "LOW": "low",
    "WARN": "medium",
    "MEDIUM": "medium",
    "HIGH": "high",
    "CRITICAL": "critical",
    "FATAL": "critical",
}


def _iter_checks(node: Any) -> Iterator[dict[str, Any]]:
    """Yield every check object in a (possibly nested) testssl document."""
    if isinstance(node, dict):
        if "id" in node and "severity" in node:
            yield node
            return
        for value in node.values():
            yield from _iter_checks(value)
    elif isinstance(node, list):
        for value in node:
            yield from _iter_checks(value)


def parse_testssl_json(output: str) -> list[dict[str, Any]]:
    """Parse testssl.sh JSON output (``--jsonfile-pretty`` or ``--jsonfile``).

    Checks repeated across sections (e.g. the cipher lists appear under both
    ``ciphers`` and ``cipherTests``) are returned once.
    """
    findings: list[dict[str, Any]] = []
    if not output.strip():
        return findings

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return findings

    seen: set[tuple[str, str, str, str]] = set()
    for item in _iter_checks(data):
        check_id = str(item.get("id") or "").strip()
        if not check_id:
            continue

        severity_raw = str(item.get("severity", "INFO")).upper()
        finding_text = str(item.get("finding", "") or "")
        ip = str(item.get("ip", "") or "")
        key = (check_id, severity_raw, finding_text, ip)
        if key in seen:
            continue
        seen.add(key)

        findings.append({
            "type": "tls_check",
            "id": check_id,
            "ip": ip,
            "port": str(item.get("port", "443") or "443"),
            "severity": _SEVERITY_MAP.get(severity_raw, "info"),
            "finding": finding_text,
            "cve": item.get("cve", ""),
            "cwe": item.get("cwe", ""),
        })

    return findings
