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
                    findings.append(
                        {
                            "type": "vulnerability",
                            "id": str(vuln.get("id", "")),
                            "osvdb": str(vuln.get("osvdb", "")),
                            "url": str(vuln.get("url", "")),
                            "method": str(vuln.get("method", "GET")),
                            "msg": str(vuln.get("msg", "")),
                            "references": str(vuln.get("references", "")),
                        }
                    )
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return findings


#: ``+ Key: value`` lines Nikto prints about the run itself, not findings.
_INFORMATIONAL_PREFIXES = (
    "Target IP:",
    "Target Hostname:",
    "Target Port:",
    "Platform:",
    "Start Time:",
    "End Time:",
    "Server:",
    "Multiple IPs found:",
    "SSL Info:",
    "Root page",
    "Allowed HTTP Methods:",
    "No CGI Directories found",
    "host(s) tested",
    "NOTE:",
    "Nikto",
    "Testing:",
)

_ID_RE = re.compile(r"^\[(\d+)\]\s*(.*)$")
_OSVDB_RE = re.compile(r"^OSVDB-(\d+):\s*(.*)$")
_URL_RE = re.compile(r"^(/[^\s:]*|https?://[^\s:]+):\s+(.*)$")


def parse_nikto_text(output: str) -> list[dict[str, Any]]:
    """Parse Nikto plain-text output (the default screen report).

    Nikto prints its findings on stdout when no report format/file is
    configured.  Lines look like::

        + [011799] /: An alt-svc header was found ...
        + OSVDB-XXXX: /path: Description of the finding.
        + /path: Description without OSVDB.

    Run metadata (``+ Target IP:``, ``+ Server:``, ``+ Start Time:`` …) is
    skipped: it describes the run, not a finding.  Lines with no identifier and
    no path are dropped for the same reason.
    """
    findings: list[dict[str, Any]] = []

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line.startswith("+"):
            continue
        msg = line[1:].strip()
        if not msg or msg.startswith(_INFORMATIONAL_PREFIXES):
            continue

        identifier = ""
        id_match = _ID_RE.match(msg)
        if id_match:
            identifier = f"OSVDB-{id_match.group(1)}"
            msg = id_match.group(2).strip()
        else:
            osvdb_match = _OSVDB_RE.match(msg)
            if osvdb_match:
                identifier = f"OSVDB-{osvdb_match.group(1)}"
                msg = osvdb_match.group(2).strip()

        url = ""
        url_match = _URL_RE.match(msg)
        if url_match:
            url = url_match.group(1)
            msg = url_match.group(2).strip()

        # Only lines with an identifier or a path are actual findings.
        if not identifier and not url:
            continue
        if not msg:
            continue

        numeric_id = identifier.split("-", 1)[1] if identifier else ""
        findings.append(
            {
                "type": "vulnerability",
                "id": identifier,
                "osvdb": numeric_id,
                "url": url,
                "method": "GET",
                "msg": msg,
                "references": f"https://osvdb.org/{numeric_id}" if numeric_id else "",
            }
        )

    return findings
