"""Nikto output parser.

Parses ``nikto -Format json`` or plain-text output.
"""

from __future__ import annotations

import json
import re
from typing import Any


def parse_nikto_json(output: str) -> list[dict[str, Any]]:
    """Parse Nikto JSON output (``-Format json``)."""
    findings: list[dict[str, Any]] = []
    if not output.strip():
        return findings
    try:
        data = json.loads(output)
        # Nikto JSON wraps vulnerabilities under host results
        hosts = data if isinstance(data, list) else [data]
        for host_data in hosts:
            vulns = host_data.get("vulnerabilities", [])
            if isinstance(vulns, list):
                for vuln in vulns:
                    findings.append({
                        "type": "vulnerability",
                        "id": str(vuln.get("id", "")),
                        "osvdb": str(vuln.get("osvdb", "")),
                        "url": str(vuln.get("url", "")),
                        "method": str(vuln.get("method", "GET")),
                        "msg": str(vuln.get("msg", "")),
                        "references": str(vuln.get("references", "")),
                    })
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return findings


def parse_nikto_text(output: str) -> list[dict[str, Any]]:
    """Parse Nikto plain-text output.

    Nikto text output lines look like::

        + OSVDB-XXXX: /path: Description of the finding.
        + /path: Description without OSVDB.
    """
    findings: list[dict[str, Any]] = []
    osvdb_re = re.compile(r"^\+\s+(?:OSVDB-(\d+):\s+)?(.+)$")

    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("+"):
            continue
        m = osvdb_re.match(line)
        if not m:
            continue
        osvdb = m.group(1) or ""
        msg = m.group(2).strip()

        # Skip informational lines
        if msg.startswith("Target IP:") or msg.startswith("Target Port:"):
            continue

        url = ""
        url_match = re.match(r"^(/[^\s:]*|https?://[^\s:]*): (.+)$", msg)
        if url_match:
            url = url_match.group(1)
            msg = url_match.group(2)

        findings.append({
            "type": "vulnerability",
            "id": f"OSVDB-{osvdb}" if osvdb else "",
            "osvdb": osvdb,
            "url": url,
            "method": "GET",
            "msg": msg,
            "references": f"https://osvdb.org/{osvdb}" if osvdb else "",
        })

    return findings
