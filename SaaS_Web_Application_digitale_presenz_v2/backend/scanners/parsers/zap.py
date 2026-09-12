"""OWASP ZAP JSON output parser."""

from __future__ import annotations

import json
from typing import Any


def parse_zap_json(output: str) -> list[dict[str, Any]]:
    """Parse OWASP ZAP JSON report output."""
    findings: list[dict[str, Any]] = []
    if not output.strip():
        return findings

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return findings

    # ZAP report format: {"site": [...]}
    sites = data.get("site", [])
    if isinstance(sites, dict):
        sites = [sites]

    for site in sites:
        alerts = site.get("alerts", [])
        for alert in alerts:
            risk = str(alert.get("riskdesc", "")).split(" ")[0].lower()
            risk_map = {
                "informational": "info",
                "low": "low",
                "medium": "medium",
                "high": "high",
            }
            severity = risk_map.get(risk, "info")

            findings.append({
                "type": "zap_alert",
                "alert_id": str(alert.get("pluginid", "")),
                "name": alert.get("name", ""),
                "riskcode": str(alert.get("riskcode", "0")),
                "confidence": str(alert.get("confidence", "0")),
                "severity": severity,
                "description": alert.get("desc", ""),
                "solution": alert.get("solution", ""),
                "reference": alert.get("reference", ""),
                "instances": alert.get("instances", []),
                "cweid": str(alert.get("cweid", "")),
                "wascid": str(alert.get("wascid", "")),
            })

    return findings
