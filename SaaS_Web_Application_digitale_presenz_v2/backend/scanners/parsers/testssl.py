"""testssl.sh JSON output parser."""

from __future__ import annotations

import json
from typing import Any


def parse_testssl_json(output: str) -> list[dict[str, Any]]:
    """Parse testssl.sh JSON output (``--jsonfile``).

    testssl writes a JSON array of finding objects.
    """
    findings: list[dict[str, Any]] = []
    if not output.strip():
        return findings

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return findings

    # testssl output is an array of objects with id, ip, port, severity, finding
    items = data if isinstance(data, list) else data.get("scanResult", [])

    for item in items:
        if not isinstance(item, dict):
            continue
        severity_raw = str(item.get("severity", "INFO")).upper()
        # Map testssl severities to our model
        severity_map = {
            "INFO": "info",
            "OK": "info",
            "LOW": "low",
            "WARN": "medium",
            "MEDIUM": "medium",
            "HIGH": "high",
            "CRITICAL": "critical",
            "FATAL": "critical",
        }
        severity = severity_map.get(severity_raw, "info")

        findings.append({
            "type": "tls_check",
            "id": item.get("id", ""),
            "ip": item.get("ip", ""),
            "port": item.get("port", "443"),
            "severity": severity,
            "finding": item.get("finding", ""),
            "cve": item.get("cve", ""),
            "cwe": item.get("cwe", ""),
        })

    return findings
