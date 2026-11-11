"""WhatWeb JSON output parser."""

from __future__ import annotations

import json
from typing import Any


def parse_whatweb_json(output: str) -> list[dict[str, Any]]:
    """Parse WhatWeb JSON output (``--log-json``).

    WhatWeb writes either a JSON array or a single JSON object per line.
    """
    findings: list[dict[str, Any]] = []
    if not output.strip():
        return findings

    raw = output.strip()

    # Try as JSON array first.
    if raw.startswith("["):
        try:
            items = json.loads(raw)
            if isinstance(items, list):
                for item in items:
                    findings.extend(_extract_whatweb_item(item))
            return findings
        except json.JSONDecodeError:
            pass

    # Fallback: JSONL
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            findings.extend(_extract_whatweb_item(item))
        except json.JSONDecodeError:
            continue

    return findings


def _extract_whatweb_item(item: dict) -> list[dict[str, Any]]:
    """Extract technology findings from a WhatWeb result dict."""
    findings: list[dict[str, Any]] = []
    target = item.get("target", "")
    http_status = item.get("http_status", 0)
    plugins = item.get("plugins", {})

    for tech_name, tech_data in plugins.items():
        if not isinstance(tech_data, dict):
            continue
        # WhatWeb stores versions, strings, etc. as lists under keys
        versions = tech_data.get("version", []) or []
        strings = tech_data.get("string", []) or []
        findings.append(
            {
                "type": "technology",
                "target": target,
                "http_status": http_status,
                "technology": tech_name,
                "versions": versions if isinstance(versions, list) else [str(versions)],
                "strings": strings if isinstance(strings, list) else [str(strings)],
            }
        )

    return findings
