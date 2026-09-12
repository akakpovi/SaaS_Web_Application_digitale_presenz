"""Nuclei JSON Lines output parser.

Nuclei writes one JSON object per line (JSONL) when ``-json`` flag is used.
"""

from __future__ import annotations

import json
from typing import Any


def parse_nuclei_jsonl(output: str) -> list[dict[str, Any]]:
    """Parse Nuclei JSONL output (``-json``)."""
    findings: list[dict[str, Any]] = []
    if not output.strip():
        return findings

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        info = item.get("info", {})
        findings.append({
            "type": "nuclei_template",
            "template_id": item.get("template-id", ""),
            "template_path": item.get("template-path", ""),
            "name": info.get("name", ""),
            "severity": info.get("severity", "info").lower(),
            "tags": info.get("tags", []),
            "description": info.get("description", ""),
            "reference": info.get("reference", []),
            "matched_at": item.get("matched-at", ""),
            "matcher_name": item.get("matcher-name", ""),
            "extracted_results": item.get("extracted-results", []),
            "curl_command": item.get("curl-command", ""),
            "host": item.get("host", ""),
            "ip": item.get("ip", ""),
            "timestamp": item.get("timestamp", ""),
        })

    return findings
