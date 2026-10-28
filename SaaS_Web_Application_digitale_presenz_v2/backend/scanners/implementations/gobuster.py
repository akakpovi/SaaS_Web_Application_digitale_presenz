"""Gobuster directory/file enumeration adapter.

Scope
-----
Enumeration is deliberately bounded: one small, versioned wordlist shipped by
the sandbox image (Debian ``dirb``: ``common.txt``), a fixed low thread count
and a short per-request timeout.  The adapter never accepts a wordlist path from
scan input — it is read from ``SCANNER_CONFIG`` only.

Completeness
------------
Gobuster is silent when a complete run finds nothing, so an empty report is a
valid result here (``requires_output=False``).  A non-zero exit code, a sandbox
kill or a truncated report is reported as incomplete: the enumeration did not
cover the wordlist and proves nothing about the paths it never tested.
"""

from __future__ import annotations

import logging
import re
import secrets
from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings

from scanners.base import (
    BaseScanner,
    FindingStatus,
    NormalizedFinding,
    ScanContext,
    ScanOutcome,
    ScanResult,
    ScannerType,
    Severity,
)
from scanners.exceptions import TargetValidationError
from scanners.implementations.tool_run import (
    SandboxError,
    ToolRun,
    build_outcome,
    evaluate_completeness,
    resolve_target,
    run_tool,
    target_validation_outcome,
    unavailable_outcome,
)

logger = logging.getLogger(__name__)

#: Safe, non-destructive wordlist baked into the sandbox image (Debian dirb).
#: 4614 paths — bounded enough to finish inside the step budget with ten
#: threads, and versioned with the image instead of downloaded at scan time.
DEFAULT_WORDLIST = "/usr/share/dirb/wordlists/common.txt"

#: Paths whose exposure is treated as high severity.
_SENSITIVE_PATHS = frozenset({
    "/admin", "/.env", "/backup", "/config", "/.git", "/wp-admin",
})

#: Gobuster clears its progress line with ANSI escapes even under
#: ``--no-color`` when stdout is not a terminal (observed with 3.6 in the
#: sandbox image: ``\r\x1b[2K/admin (Status: 200)``).  Left in place, the
#: escape prefix makes a real result look like a banner line and the path is
#: silently dropped.
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

#: Prefix of the random path used to detect a catch-all (soft-404) response.
_SOFT_404_PREFIX = "/.presence-soft404-"

#: The probe is a single request; it must never consume the gobuster budget.
_SOFT_404_PROBE_TIMEOUT_S = 10.0


@dataclass(frozen=True)
class Soft404Probe:
    """Result of the random-path probe used before directory enumeration."""

    sampled_path: str
    status_code: int | None = None
    excluded_length: int | None = None
    error: str = ""


def probe_soft_404(
    target: str,
    *,
    timeout: float = _SOFT_404_PROBE_TIMEOUT_S,
) -> Soft404Probe:
    """Detect a catch-all 200 response before Gobuster runs.

    A SPA (or an over-permissive rewrite rule) answers 200 for a path that
    cannot exist.  Gobuster then refuses to continue because every directory
    looks real.  The response body length of one random path is enough to tell
    Gobuster to ignore that length with ``--exclude-length``.  A real 404 (or
    any non-200/empty response) returns no exclusion.

    This probe never raises: a failed probe must leave the scanner in its
    previous, conservative behaviour (no exclusion, run reported incomplete
    if Gobuster exits 1).
    """
    sampled_path = f"{_SOFT_404_PREFIX}{secrets.token_hex(8)}"
    url = f"{target.rstrip('/')}{sampled_path}"
    try:
        response = requests.get(
            url,
            timeout=timeout,
            allow_redirects=False,
            headers={"User-Agent": "Presence-Scanner/1.0"},
        )
    except requests.RequestException as exc:
        logger.warning(
            "gobuster soft-404 probe failed target=%s error=%s",
            target,
            exc.__class__.__name__,
        )
        return Soft404Probe(sampled_path=sampled_path, error=exc.__class__.__name__)

    body_length = len(response.content or b"")
    if response.status_code == 200 and body_length > 0:
        return Soft404Probe(
            sampled_path=sampled_path,
            status_code=response.status_code,
            excluded_length=body_length,
        )
    return Soft404Probe(
        sampled_path=sampled_path,
        status_code=response.status_code,
    )


def _parse_gobuster_output(output: str) -> list[dict[str, Any]]:
    """Parse Gobuster plain-text output.

    Gobuster 3.x prints one result per line::

        /admin                (Status: 301) [Size: 0]
        http://host/.git      (Status: 403) [Size: 281]

    Lines that carry no path (banners, progress, errors) are ignored.
    """
    findings: list[dict[str, Any]] = []
    for raw_line in output.splitlines():
        line = _ANSI_ESCAPE_RE.sub("", raw_line).strip()
        if not line:
            continue
        # Errors and banner lines start with a tag/level prefix.
        if line.startswith("["):
            continue

        status_code = 0
        size = 0
        path = line
        if "(Status:" in line:
            head, _, tail = line.partition("(Status:")
            path = head.strip()
            code_text = tail.strip().split()[0] if tail.strip() else ""
            try:
                status_code = int(code_text.rstrip(")"))
            except ValueError:
                status_code = 0
            if "[Size:" in tail:
                size_text = tail.split("[Size:", 1)[1].strip()
                size_text = size_text.split("]")[0].strip()
                try:
                    size = int(size_text)
                except ValueError:
                    size = 0

        if not path or not (path.startswith("/") or path.startswith("http")):
            continue

        findings.append({
            "path": path,
            "status_code": status_code,
            "size": size,
        })
    return findings


class GobusterScanner(BaseScanner):
    """Gobuster directory enumeration scanner adapter."""

    name = "gobuster"
    scanner_type = ScannerType.CLI
    _binary = "gobuster"

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("gobuster", {}).get("timeout", 45)

    def execute(
        self,
        domain: str,
        context: ScanContext | None = None,
    ) -> ScanOutcome:
        """Run Gobuster exactly once and return result + normalized findings."""
        if not self.is_available():
            return build_outcome(
                self,
                run=ToolRun(exit_code=-1),
                findings=[
                    NormalizedFinding(
                        check_code="gobuster.unavailable",
                        category="security",
                        severity=Severity.INFO,
                        status=FindingStatus.NOT_APPLICABLE,
                        title="Gobuster not available",
                        recommendation="Install gobuster for directory enumeration.",
                    )
                ],
                message="Gobuster not available — skipped",
                status="neutral",
                recommendation="Install gobuster for directory enumeration.",
                scan_complete=False,
                partial_reason="unavailable",
            )

        try:
            target_info = resolve_target(domain, context)
        except TargetValidationError as exc:
            return target_validation_outcome(self, error=str(exc))

        cfg = getattr(settings, "SCANNER_CONFIG", {}).get("gobuster", {})
        probe: Soft404Probe | None = None
        if cfg.get("soft_404_detection", True):
            probe_timeout = _SOFT_404_PROBE_TIMEOUT_S
            if context is not None:
                probe_timeout = max(
                    1.0, min(probe_timeout, context.remaining_seconds())
                )
            probe = probe_soft_404(target_info.url, timeout=probe_timeout)

        try:
            run = run_tool(
                self,
                self.build_command(
                    target_info.url,
                    soft404_length=(
                        probe.excluded_length if probe is not None else None
                    ),
                ),
                context=context,
            )
        except SandboxError as exc:
            logger.error("Gobuster sandbox unavailable: %s", exc)
            return unavailable_outcome(self, reason=str(exc))

        # A quiet complete run prints nothing when no path matches.
        complete, reason = evaluate_completeness(
            run, ok_exit_codes=(0,), requires_output=False
        )
        parsed = _parse_gobuster_output(run.stdout)
        findings = self.normalize(parsed)

        return build_outcome(
            self,
            run=run,
            findings=findings,
            message=(
                f"Gobuster found {len(parsed)} path(s)"
                if complete
                else f"Gobuster scan incomplete ({reason}): "
                f"{len(parsed)} path(s) seen so far"
            ),
            status="neutral" if complete else "warning",
            scan_complete=complete,
            partial_reason=reason,
            paths_found=len(parsed),
            wordlist=self.wordlist,
            raw_report=run.stdout or None,
            raw_report_format="gobuster-text",
            raw_report_meta={
                "paths_found": len(parsed),
                "wordlist": self.wordlist,
            },
            soft_404_probe=(
                {
                    "sampled_path": probe.sampled_path,
                    "status_code": probe.status_code,
                    "excluded_length": probe.excluded_length,
                    "error": probe.error,
                }
                if probe is not None
                else None
            ),
            soft_404_excluded_length=(
                probe.excluded_length if probe is not None else None
            ),
        )

    @property
    def wordlist(self) -> str:
        """Wordlist path, from settings only (never from scan input)."""
        cfg = getattr(settings, "SCANNER_CONFIG", {}).get("gobuster", {})
        return str(cfg.get("wordlist") or DEFAULT_WORDLIST)

    def scan(self, domain: str) -> ScanResult:
        return self.execute(domain).result

    def scan_findings(
        self,
        domain: str,
        result: ScanResult | None = None,
    ) -> list[NormalizedFinding]:
        """Legacy entry point; the tool runs once via :meth:`execute`."""
        return self.execute(domain).findings

    def build_command(
        self,
        target: str,
        options: dict | None = None,
        *,
        soft404_length: int | None = None,
    ) -> list[str]:
        cfg = getattr(settings, "SCANNER_CONFIG", {}).get("gobuster", {})
        threads = int(cfg.get("threads", 10) or 10)
        request_timeout = str(cfg.get("request_timeout", "10s"))
        command = [
            "gobuster", "dir",
            "-u", target,
            "-w", self.wordlist,
            "-t", str(threads),
            "-q",                       # only results on stdout
            "--timeout", request_timeout,
            "--no-color",
        ]
        if soft404_length is not None:
            # The probe saw a 200 with this body length for a random path:
            # every hit with the same length is the catch-all page, not a
            # directory.  Other lengths remain real results.
            command.extend(["--exclude-length", str(soft404_length)])
        return command

    def parse(self, output: str) -> list[dict[str, Any]]:
        return _parse_gobuster_output(output)

    def normalize(self, parsed_results: list[dict[str, Any]]) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []

        for item in parsed_results:
            path = item.get("path", "")
            # Compare on the path component only (gobuster may echo a full URL).
            path_key = path.split("://", 1)[-1] if "://" in path else path
            path_key = "/" + path_key.split("/", 3)[-1] if path_key.count("/") > 2 else path_key
            sensitive = path_key in _SENSITIVE_PATHS

            findings.append(NormalizedFinding(
                check_code=(
                    "gobuster.path."
                    + (path_key.strip("/").replace("/", "_") or "root")
                ),
                category="security",
                severity=Severity.HIGH if sensitive else Severity.LOW,
                status=FindingStatus.FAIL if sensitive else FindingStatus.WARNING,
                title=f"Directory/file found: {path}",
                description=(
                    f"Path '{path}' is publicly accessible "
                    f"(HTTP {item.get('status_code', '?')})"
                ),
                evidence=item,
                recommendation=(
                    f"Restrict access to '{path}' or remove it if not needed."
                    if sensitive else ""
                ),
            ))

        return findings


gobuster_scanner = GobusterScanner()
