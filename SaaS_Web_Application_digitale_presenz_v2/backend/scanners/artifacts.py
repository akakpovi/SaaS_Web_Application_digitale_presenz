"""Private archival of raw scanner reports.

Nuclei already exposes its JSONL on stdout, including the lines emitted before a
timeout or a sandbox kill.  That output is the only artefact that lets an
operator diagnose *why* a run was partial, so it must be kept — but it is
untrusted scanner output that can contain cookies, bearer tokens, query-string
credentials and personal data.

This module therefore:

* redacts the report before writing it (JSON keys and raw HTTP/header text);
* writes it under a dedicated, non-public directory with ``0700``/``0600``
  permissions and no secret in the filename;
* de-duplicates by content hash, so a retry of the same report does not create
  a second copy;
* stores per-run diagnostic metadata in a sidecar JSON file;
* exposes a bounded retention cleanup.

Archiving is deliberately best-effort: a storage failure must never turn a
successful scan into a failed one.  The caller persists ``ArchiveResult`` in
``ScannerRun.metadata`` so a failure is visible instead of silent.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

ARCHIVE_SCHEMA_VERSION = 1
DEFAULT_MAX_BYTES = 8 * 1024 * 1024
DEFAULT_RETENTION_DAYS = 30
REDACTED = "[REDACTED]"

# A key is sensitive when it is a complete token surrounded by ``_``/``-`` or
# string boundaries.  This intentionally catches ``Authorization``,
# ``set-cookie``, ``x-api-key``, ``access_token`` … without redacting ordinary
# fields such as ``template-id`` or ``matched-at``.
_SENSITIVE_KEY_RE = re.compile(
    r"(?i)(?:^|[_-])("
    r"authorization|proxy[_-]?authorization|cookie|set[_-]?cookie|"
    r"x[_-]?api[_-]?key|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"id[_-]?token|auth[_-]?token|token|password|passwd|passphrase|secret|"
    r"client[_-]?secret|session[_-]?id|session|auth|csrf|xsrf|jwt|bearer|"
    r"private[_-]?key"
    r")(?:$|[_-])"
)

_SENSITIVE_QUERY_RE = re.compile(
    r"(?i)([?&](?:"
    r"code|state|token|access_token|refresh_token|id_token|session|"
    r"password|passwd|secret|api_key|apikey|key|jwt|sig|signature|auth"
    r")=)([^&#\s\"'<>]+)"
)
_HEADER_LINE_RE = re.compile(
    r"(?im)^(\s*(?:authorization|proxy-authorization|cookie|set-cookie|"
    r"x-api-key)\s*:\s*)(.*)$"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
)
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)
_SECRET_TOKEN_RE = re.compile(
    r"\b(?:sk|pk|rk|ghp|gho|ghu|ghs|ghr|glpat|xox[baprs]|AKIA)"
    r"[A-Za-z0-9_-]{12,}\b"
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|"
    r"password|passwd|secret|client[_-]?secret)\s*[=:]\s*)[\"']?[^\"'\s,}]+"
)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)


class ArchiveConfigurationError(RuntimeError):
    """The archive directory is missing or unsafe (e.g. ``/`` or MEDIA_ROOT)."""


@dataclass(frozen=True)
class ArchiveResult:
    """Outcome of one archive attempt, safe to persist in scanner metadata."""

    status: str
    ref: str = ""
    sha256: str = ""
    bytes: int = 0
    lines: int = 0
    records: int = 0
    redactions: int = 0
    truncated: bool = False
    partial: bool = False
    retention_days: int = 0
    detail: str = ""

    def as_metadata(self) -> dict[str, Any]:
        """Return a compact, non-secret representation for ``ScannerRun``."""
        return {
            "status": self.status,
            "ref": self.ref,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "lines": self.lines,
            "records": self.records,
            "redactions": self.redactions,
            "truncated": self.truncated,
            "partial": self.partial,
            "retention_days": self.retention_days,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

def _redact_text(text: str, state: dict[str, int]) -> str:
    """Redact common credentials and PII from a free-form string."""
    if not isinstance(text, str) or not text:
        return text

    original = text
    text = _PRIVATE_KEY_RE.sub(
        lambda match: _count(state, "[REDACTED-PRIVATE-KEY]"), text
    )
    text = _HEADER_LINE_RE.sub(
        lambda match: f"{match.group(1)}{REDACTED}",
        text,
    )
    if text != original:
        state["count"] += 1

    def _query(match: re.Match[str]) -> str:
        state["count"] += 1
        return f"{match.group(1)}{REDACTED}"

    text = _SENSITIVE_QUERY_RE.sub(_query, text)
    text = _BEARER_RE.sub(lambda match: _count(state, f"Bearer {REDACTED}"), text)
    text = _JWT_RE.sub(lambda match: _count(state, "[REDACTED-JWT]"), text)
    text = _SECRET_TOKEN_RE.sub(lambda match: _count(state, "[REDACTED-KEY]"), text)
    text = _SECRET_ASSIGNMENT_RE.sub(
        lambda match: _count(state, f"{match.group(1)}{REDACTED}"), text
    )
    text = _EMAIL_RE.sub(lambda match: _count(state, "[REDACTED-EMAIL]"), text)
    return text


def _count(state: dict[str, int], replacement: str) -> str:
    state["count"] += 1
    return replacement


def _is_sensitive_key(key: Any) -> bool:
    return bool(_SENSITIVE_KEY_RE.search(str(key)))


def _redact_value(value: Any, state: dict[str, int]) -> Any:
    """Recursively redact a JSON-compatible value."""
    if isinstance(value, dict):
        cleaned: dict[Any, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(key):
                state["count"] += 1
                cleaned[key] = REDACTED
            else:
                cleaned[key] = _redact_value(item, state)
        return cleaned
    if isinstance(value, list):
        return [_redact_value(item, state) for item in value]
    if isinstance(value, str):
        return _redact_text(value, state)
    return value


def redact_report(text: str) -> tuple[str, int, int]:
    """Return ``(sanitised_text, json_records, redaction_count)``.

    Valid JSON lines are re-serialised so structural redaction is reliable.
    Invalid/truncated lines (which are common after a timeout) are kept after
    free-text redaction: they are diagnostic material, not parsed findings.
    """
    state = {"count": 0}
    records = 0
    output: list[str] = []
    had_trailing_newline = text.endswith(("\n", "\r"))

    for line in text.splitlines():
        if not line.strip():
            output.append(line)
            continue
        try:
            payload = json.loads(line)
        except (TypeError, ValueError):
            output.append(_redact_text(line, state))
            continue

        if isinstance(payload, dict):
            records += 1
            payload = _redact_value(payload, state)
            output.append(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            )
        elif isinstance(payload, list):
            records += len(payload)
            payload = _redact_value(payload, state)
            output.append(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            )
        else:
            output.append(_redact_text(line, state))

    sanitised = "\n".join(output)
    if had_trailing_newline and sanitised:
        sanitised += "\n"
    return sanitised, records, state["count"]


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _archive_root() -> Path:
    """Return the configured private archive root, rejecting unsafe paths."""
    configured = getattr(settings, "SCANNER_ARCHIVE_DIR", "") or ""
    if not configured:
        raise ArchiveConfigurationError("SCANNER_ARCHIVE_DIR is empty")
    root = Path(os.fspath(configured)).expanduser()
    if not root.is_absolute():
        root = Path(settings.BASE_DIR) / root
    root = root.resolve()

    if root == Path(root.anchor):
        raise ArchiveConfigurationError("SCANNER_ARCHIVE_DIR cannot be a filesystem root")
    media_root = getattr(settings, "MEDIA_ROOT", None)
    if media_root:
        media = Path(os.fspath(media_root)).expanduser().resolve()
        try:
            root.relative_to(media)
        except ValueError:
            pass
        else:
            raise ArchiveConfigurationError(
                "SCANNER_ARCHIVE_DIR must not be inside MEDIA_ROOT"
            )
    return root


def _ensure_private_dir(path: Path) -> None:
    """Create *path* and keep every archive directory owner-only.

    ``Path.mkdir(parents=True, mode=0o700)`` only applies the mode to the
    final component: intermediate ``scanner/YYYY/MM`` directories would be
    created with 0755 and reveal archive names to other local users.  Walk
    back up to the archive root (never beyond it) and enforce 0700 there too.
    """
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    root = _archive_root()
    current = path
    while True:
        try:
            current.relative_to(root)
        except ValueError:
            break
        os.chmod(current, 0o700)
        if current == root:
            break
        current = current.parent


def _write_private(path: Path, payload: bytes) -> None:
    """Atomically write *payload* with owner-only permissions."""
    _ensure_private_dir(path.parent)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=".tmp-", delete=False
        ) as handle:
            temp_name = handle.name
            os.chmod(temp_name, 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        os.chmod(path, 0o600)
    finally:
        if temp_name and os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass


def _same_content(path: Path, payload: bytes) -> bool:
    try:
        if path.stat().st_size != len(payload):
            return False
        return path.read_bytes() == payload
    except OSError:
        return False


def _safe_component(value: str, fallback: str = "scanner") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "")).strip("-")
    return (cleaned or fallback)[:48]


def _iso_utc(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).isoformat()


def _truncate_bytes(text: str, limit: int) -> tuple[str, bool]:
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text, False
    return encoded[:limit].decode("utf-8", errors="replace"), True


def _count_json_records(text: str) -> int:
    count = 0
    for line in text.splitlines():
        try:
            payload = json.loads(line)
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            count += 1
        elif isinstance(payload, list):
            count += len(payload)
    return count


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def archive_report(
    *,
    scanner_name: str,
    scan_id: int | None,
    scanner_run_id: int | None,
    raw_report: str | None,
    report_format: str = "",
    diagnostics: dict[str, Any] | None = None,
    complete: bool = True,
    partial_reason: str = "",
) -> ArchiveResult:
    """Archive one raw report; never raises.

    ``raw_report=""`` is archived only when ``complete=True``: an empty
    complete report is a legitimate "no findings" result.  An empty report
    from an incomplete run is *not* fabricated into an archive; the result is
    ``unavailable`` and the caller can persist that limitation.
    """
    retention_days = max(
        0,
        int(getattr(settings, "SCANNER_ARCHIVE_RETENTION_DAYS", DEFAULT_RETENTION_DAYS) or 0),
    )
    if not getattr(settings, "SCANNER_ARCHIVE_ENABLED", False):
        return ArchiveResult(
            status="disabled", partial=not complete, retention_days=retention_days
        )

    scanner = _safe_component(scanner_name)
    scan_key = scanner_run_id or 0
    scan_number = scan_id or 0

    if raw_report is None or (not raw_report and not complete):
        reason = "empty_report" if raw_report == "" else "no_raw_report"
        logger.warning(
            "scanner_archive_unavailable scanner=%s scan=%s run=%s reason=%s",
            scanner,
            scan_number,
            scan_key,
            reason,
        )
        return ArchiveResult(
            status="unavailable",
            partial=not complete,
            retention_days=retention_days,
            detail=reason,
        )

    if isinstance(raw_report, bytes):
        raw_report = raw_report.decode("utf-8", errors="replace")

    max_bytes = max(
        1,
        int(getattr(settings, "SCANNER_ARCHIVE_MAX_BYTES", DEFAULT_MAX_BYTES) or DEFAULT_MAX_BYTES),
    )

    try:
        sanitised, _, redactions = redact_report(raw_report)
        sanitised, cut_by_redaction = _truncate_bytes(sanitised, max_bytes)
        truncated = len(raw_report.encode("utf-8")) > max_bytes or cut_by_redaction
        payload = sanitised.encode("utf-8")
        sha256 = hashlib.sha256(payload).hexdigest()
        records = _count_json_records(sanitised)
        lines = len(sanitised.splitlines())

        root = _archive_root()
        _ensure_private_dir(root)
        day = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        ref = f"{scanner}/{day}/{scanner}-scan{scan_number}-{sha256[:16]}.jsonl"
        final_path = root / ref
        _ensure_private_dir(final_path.parent)

        if final_path.exists() and _same_content(final_path, payload):
            status = "reused"
        else:
            _write_private(final_path, payload)
            status = "stored"

        sidecar_ref = (
            f"{scanner}/{day}/"
            f"{scanner}-scan{scan_number}-run{scan_key}-{sha256[:16]}.meta.json"
        )
        sidecar_path = root / sidecar_ref
        _ensure_private_dir(sidecar_path.parent)

        safe_diagnostics = _redact_value(diagnostics or {}, {"count": 0})
        sidecar = {
            "schema_version": ARCHIVE_SCHEMA_VERSION,
            "scanner": scanner,
            "scan_id": scan_number,
            "scanner_run_id": scan_key,
            "report_format": _safe_component(report_format, "jsonl"),
            "archive_ref": ref,
            "sha256": sha256,
            "bytes": len(payload),
            "lines": lines,
            "records": records,
            "redactions": redactions,
            "truncated": truncated,
            "complete": bool(complete),
            "partial": not bool(complete),
            "partial_reason": str(partial_reason or "")[:128],
            "created_at": _iso_utc(),
            "retention_days": retention_days,
            "diagnostics": safe_diagnostics,
        }
        _write_private(
            sidecar_path,
            (json.dumps(sidecar, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n").encode(
                "utf-8"
            ),
        )

        return ArchiveResult(
            status=status,
            ref=ref,
            sha256=sha256,
            bytes=len(payload),
            lines=lines,
            records=records,
            redactions=redactions,
            truncated=truncated,
            partial=not bool(complete),
            retention_days=retention_days,
        )
    except ArchiveConfigurationError as exc:
        logger.error(
            "scanner_archive_config_error scanner=%s scan=%s run=%s: %s",
            scanner,
            scan_number,
            scan_key,
            exc,
        )
        return ArchiveResult(
            status="failed",
            partial=not bool(complete),
            retention_days=retention_days,
            detail="unsafe_archive_dir",
        )
    except Exception as exc:  # storage failures must not break the scan
        logger.exception(
            "scanner_archive_failed scanner=%s scan=%s run=%s error=%s",
            scanner,
            scan_number,
            scan_key,
            type(exc).__name__,
        )
        return ArchiveResult(
            status="failed",
            partial=not bool(complete),
            retention_days=retention_days,
            detail=type(exc).__name__,
        )


def prune_scan_archives(
    *,
    retention_days: int | None = None,
    now: datetime | None = None,
) -> dict[str, int | bool]:
    """Delete archive files older than the configured retention.

    Only regular files below the dedicated archive root are considered;
    symlinks are never followed.  A retention of ``0`` disables deletion.
    """
    configured_days = getattr(
        settings, "SCANNER_ARCHIVE_RETENTION_DAYS", DEFAULT_RETENTION_DAYS
    )
    days = max(0, int(retention_days if retention_days is not None else configured_days or 0))
    if days == 0:
        return {"enabled": False, "deleted": 0, "kept": 0, "errors": 0}

    try:
        root = _archive_root()
    except ArchiveConfigurationError:
        logger.exception("scanner_archive_prune_invalid_root")
        return {"enabled": True, "deleted": 0, "kept": 0, "errors": 1}
    if not root.exists():
        return {"enabled": True, "deleted": 0, "kept": 0, "errors": 0}

    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    cutoff_ts = cutoff.timestamp()
    deleted = kept = errors = 0
    directories: list[Path] = []

    for path in root.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_dir():
            directories.append(path)
            continue
        if not path.is_file():
            continue
        try:
            if path.stat().st_mtime < cutoff_ts:
                path.unlink()
                deleted += 1
            else:
                kept += 1
        except OSError:
            errors += 1
            logger.warning("scanner_archive_prune_failed path=%s", path.name)

    # Remove only empty directories; a failed rmdir leaves the tree untouched.
    for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        if directory == root:
            continue
        try:
            directory.rmdir()
        except OSError:
            pass

    logger.info(
        "scanner_archive_pruned retention_days=%d deleted=%d kept=%d errors=%d",
        days,
        deleted,
        kept,
        errors,
    )
    return {"enabled": True, "deleted": deleted, "kept": kept, "errors": errors}
