"""Canonical finding de-duplication for the scenario-C journey pipeline.

The stage-2 pipeline runs a content-verifying template scan (Nuclei with the
selected and Presence templates) before Gobuster enumerates paths.  The same
resource can therefore be reported twice: a template proves that
``/.git/config`` is a real Git configuration, while Gobuster only proves that
``/.git/config`` answers with a non-404 status.

Policies implemented here (no schema change):

* two content findings are the same problem only when category, check code and
  URL are identical;
* each missing security header keeps its own check code, so the ten findings
  produced by ``http-missing-security-headers`` are never collapsed;
* a Gobuster path which a content finding already explained is attached to that
  finding as complementary evidence instead of creating a second finding;
* ``robots.txt`` and "sensitive paths disclosed in robots.txt" use different
  check codes and therefore remain two distinct problems.

Only the stage-2 pipeline enables this behaviour; classic scans keep their
historical findings unchanged.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

#: Prefix used by :class:`scanners.implementations.gobuster.GobusterScanner`.
PATH_DISCOVERY_PREFIX = "gobuster.path."

#: Ordering used when two findings share the same canonical identity.
_SEVERITY_RANK = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def severity_rank(value: str) -> int:
    """Rank a severity for duplicate resolution (unknown sorts lowest)."""
    return _SEVERITY_RANK.get(str(value or "").strip().lower(), 0)


def finding_dedup_key(
    category: str,
    check_code: str,
    url: str,
) -> tuple[str, str, str]:
    """Return the canonical identity of one content finding."""
    normalized_url = str(url or "").strip().rstrip("/").lower()
    return (
        str(category or "").strip().lower(),
        str(check_code or "").strip().lower(),
        normalized_url,
    )


def canonical_path(value: str) -> str:
    """Return the comparable path component of a URL or Gobuster result."""
    text = str(value or "").strip()
    if "://" in text:
        text = urlsplit(text).path or "/"
    else:
        text = text.split("?", 1)[0].split("#", 1)[0]
    text = "/" + text.strip("/")
    return text.rstrip("/").lower() or "/"


def is_path_discovery(finding: Any) -> bool:
    """True for a Gobuster path finding (discovery, not content proof)."""
    return str(getattr(finding, "check_code", "") or "").startswith(
        PATH_DISCOVERY_PREFIX
    )


def finding_url(finding: Any) -> str:
    """Best-effort URL of a content finding, from its structured evidence."""
    evidence = getattr(finding, "evidence", None)
    if not isinstance(evidence, dict):
        return ""
    for key in ("matched_at", "url", "endpoint"):
        value = str(evidence.get(key) or "").strip()
        if value:
            return value
    return ""


def finding_path(finding: Any) -> str:
    """Canonical resource path of a finding, or ``""`` when unknown."""
    url = finding_url(finding)
    if url:
        return canonical_path(url)
    evidence = getattr(finding, "evidence", None)
    if isinstance(evidence, dict):
        path = str(evidence.get("path") or "").strip()
        if path:
            return canonical_path(path)
    return ""


def merge_complementary_evidence(target: Any, source: Any) -> bool:
    """Attach *source* to *target* as complementary evidence.

    Returns ``True`` when the target changed.  Secrets and response bodies are
    never copied: only the discovery fact (path, status, size) is kept.
    """
    evidence = getattr(target, "evidence", None)
    if not isinstance(evidence, dict):
        evidence = {}
    source_evidence = getattr(source, "evidence", None)
    if not isinstance(source_evidence, dict):
        source_evidence = {}

    entry = {
        "source": "gobuster",
        "path": str(source_evidence.get("path") or ""),
        "status_code": source_evidence.get("status_code"),
        "size": source_evidence.get("size"),
    }
    merged = dict(evidence)
    entries = list(merged.get("complementary_evidence") or [])
    if entry not in entries:
        entries.append(entry)
    merged["complementary_evidence"] = entries
    target.evidence = merged
    return True
