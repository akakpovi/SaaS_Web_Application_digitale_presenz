"""OWASP ZAP JSON output parser.

Two payloads are supported:

* the report produced by ``zap-baseline.py -J report.json`` (``site`` list);
* the response of ``/JSON/core/view/alerts/`` (root ``alerts`` list).

Both are normalised to the same internal dictionaries so the adapter's
``normalize()`` stays transport-agnostic.
"""

from __future__ import annotations

import json
from typing import Any

_RISK_BY_CODE = {
    "0": "info",
    "1": "low",
    "2": "medium",
    "3": "high",
}

_RISK_BY_LABEL = {
    "informational": "info",
    "info": "info",
    "low": "low",
    "medium": "medium",
    "high": "high",
}


def _severity(alert: dict[str, Any]) -> str:
    """Resolve the severity from ``riskdesc``, ``risk`` or ``riskcode``."""
    risk_label = str(alert.get("riskdesc", "")).split(" ")[0].strip().lower()
    if risk_label in _RISK_BY_LABEL:
        return _RISK_BY_LABEL[risk_label]

    risk_label = str(alert.get("risk", "")).strip().lower()
    if risk_label in _RISK_BY_LABEL:
        return _RISK_BY_LABEL[risk_label]

    return _RISK_BY_CODE.get(str(alert.get("riskcode", "")).strip(), "info")


def _normalise_alert(alert: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "zap_alert",
        "alert_id": str(alert.get("pluginid") or alert.get("pluginId") or ""),
        "name": str(alert.get("name", "") or ""),
        "riskcode": str(alert.get("riskcode", "") or ""),
        "confidence": str(alert.get("confidence", "") or ""),
        "severity": _severity(alert),
        "description": str(alert.get("desc") or alert.get("description") or ""),
        "solution": str(alert.get("solution", "") or ""),
        "reference": str(alert.get("reference", "") or ""),
        "instances": alert.get("instances", []) or [],
        "cweid": str(alert.get("cweid", "") or ""),
        "wascid": str(alert.get("wascid", "") or ""),
    }


def parse_zap_json(output: str) -> list[dict[str, Any]]:
    """Parse ZAP JSON output and return one dict per alert."""
    if not output or not output.strip():
        return []

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, dict):
        return []

    alerts: list[Any] = []

    # Core API: {"alerts": [...]}
    root_alerts = data.get("alerts")
    if isinstance(root_alerts, list):
        alerts.extend(root_alerts)

    # Report: {"site": [{"alerts": [...]}]}
    sites = data.get("site", [])
    if isinstance(sites, dict):
        sites = [sites]
    if isinstance(sites, list):
        for site in sites:
            if isinstance(site, dict) and isinstance(site.get("alerts"), list):
                alerts.extend(site["alerts"])

    findings: list[dict[str, Any]] = []
    for alert in alerts:
        if isinstance(alert, dict):
            findings.append(_normalise_alert(alert))

    return findings
