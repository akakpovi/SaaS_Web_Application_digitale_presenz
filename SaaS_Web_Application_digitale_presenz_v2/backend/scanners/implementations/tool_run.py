"""Single-run execution helpers for the external CLI scanner adapters.

Why this module exists
----------------------
The orchestrator runs a scanner through ``BaseScanner.execute()``.  The
default implementation calls ``scan()`` and then ``scan_findings()``, and the
legacy adapters re-ran the external tool in *both* methods: every advanced
scanner therefore attacked the target twice per scan, which doubled its wall
clock and its footprint on the customer's site.

The helpers below run the tool exactly once and return both artefacts
(``ScanResult`` for the health-score bridge, ``NormalizedFinding`` list for the
score engine and for ``SecurityFinding`` ingestion) together with the
completeness facts the orchestrator needs to choose between ``COMPLETED``,
``PARTIAL`` and ``TIMEOUT``:

* ``timed_out`` / ``memory_exceeded`` / ``output_truncated`` come straight from
  the sandbox executor;
* an exit code outside the tool's documented "success" set, or an empty report,
  means the run proved nothing and must not resolve findings — the adapters
  report ``scan_complete=False`` and a machine-readable ``partial_reason``.

Nothing here decides *policy*: it only makes the truth available.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Sequence

from scanners.base import (
    FindingStatus,
    NormalizedFinding,
    ScanContext,
    ScanOutcome,
    ScanResult,
    Severity,
)
from scanners.exceptions import TargetValidationError
from scanners.executors.sandbox import (
    SandboxError,
    get_sandbox_executor,
    shared_work_dir,
)
from scanners.security.target_validator import validate_domain, validate_target

logger = logging.getLogger(__name__)

#: Upper bound for a report file written by a sandboxed tool.
REPORT_READ_LIMIT_BYTES = 4 * 1024 * 1024


@contextmanager
def report_workdir(prefix: str = "presence-tool-") -> Iterator[str]:
    """Host-visible scratch directory that can be bind-mounted into a sandbox.

    The worker and the Docker daemon must resolve the path identically, so the
    directory is created under ``SCANNER_SANDBOX_SHARED_WORK_DIR`` when one is
    configured (falling back to the worker's temp directory, which is only
    correct when the worker runs on the Docker host itself).  It is world
    writable because the sandbox runs the tool as an unprivileged user, and it
    is always removed afterwards.
    """
    root = shared_work_dir()
    workdir = tempfile.mkdtemp(prefix=prefix, dir=root or None)
    try:
        os.chmod(workdir, 0o777)
    except OSError:  # pragma: no cover - defensive
        logger.warning("Could not widen permissions on sandbox workdir %s", workdir)
    try:
        yield workdir
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def read_report_file(
    path: str,
    *,
    limit_bytes: int = REPORT_READ_LIMIT_BYTES,
) -> tuple[str, bool]:
    """Return ``(text, truncated)`` for a report written by a sandboxed tool.

    A missing or unreadable file returns ``("", False)`` so the caller can
    report "no report" explicitly instead of pretending the tool said nothing.
    """
    try:
        size = os.path.getsize(path)
    except OSError:
        return "", False
    try:
        with open(path, "rb") as handle:
            data = handle.read(limit_bytes + 1)
    except OSError:
        return "", False
    truncated = size > limit_bytes or len(data) > limit_bytes
    return data[:limit_bytes].decode("utf-8", errors="replace"), truncated


@dataclass
class ToolRun:
    """Outcome of a single sandboxed tool execution."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_ms: int = 0
    timed_out: bool = False
    memory_exceeded: bool = False
    output_truncated: bool = False
    max_output_bytes: int = 0
    killed_reason: str = ""
    #: Command that was executed, kept for diagnostics (never contains input
    #: chosen by a scanned third party: the target is a validated hostname).
    command: list[str] = field(default_factory=list)

    @classmethod
    def from_command_result(cls, result: Any, *, max_output_bytes: int = 0) -> "ToolRun":
        return cls(
            stdout=getattr(result, "stdout", "") or "",
            stderr=getattr(result, "stderr", "") or "",
            exit_code=int(getattr(result, "exit_code", -1)),
            duration_ms=int(getattr(result, "duration_ms", 0) or 0),
            timed_out=bool(getattr(result, "timed_out", False)),
            memory_exceeded=bool(getattr(result, "memory_exceeded", False)),
            output_truncated=bool(getattr(result, "output_truncated", False)),
            max_output_bytes=max_output_bytes,
            killed_reason=str(getattr(result, "killed_reason", "") or ""),
            command=list(getattr(result, "command", []) or []),
        )


def resolve_target(
    domain: str,
    context: ScanContext | None = None,
    *,
    domain_only: bool = False,
) -> Any:
    """Return the SSRF-validated target for a run.

    The orchestrator always validates the target once per scan and passes it
    through ``context.target``; direct callers (legacy ``public_checker`` paths,
    tests) get a fresh validation here.  ``domain_only`` is for tools that only
    accept a DNS name (dnsrecon).

    Raises:
        TargetValidationError: when the target is not a public, resolvable host.
    """
    if context is not None and context.target is not None:
        return context.target
    if domain_only:
        return validate_domain(domain)
    return validate_target(f"https://{domain}")


def run_tool(
    scanner: Any,
    command: Sequence[str],
    *,
    context: ScanContext | None = None,
    timeout: int | None = None,
    env_extra: dict[str, str] | None = None,
    mounts: Sequence[tuple[str, str]] | None = None,
) -> ToolRun:
    """Execute *command* in the sandbox exactly once.

    The timeout is the scanner's own budget clamped to the remaining scan
    budget (``ScanContext.effective_timeout``) and, inside the executor, to
    ``SCANNER_SANDBOX["max_timeout"]``.  Nothing here can extend it.
    """
    executor = get_sandbox_executor()
    effective_timeout = (
        context.effective_timeout(scanner.timeout)
        if context is not None
        else int(timeout or scanner.timeout)
    )
    if timeout is not None and context is None:
        effective_timeout = int(timeout)

    limits = (
        context.sandbox_limits
        if context is not None and context.sandbox_limits is not None
        else executor.limits_for(scanner.name, timeout=effective_timeout)
    )

    result = executor.run(
        command=list(command),
        limits=limits,
        scanner_name=scanner.name,
        env_extra=env_extra,
        mounts=mounts,
    )
    run = ToolRun.from_command_result(
        result, max_output_bytes=executor.max_output_bytes
    )
    logger.debug(
        "scanner tool run scanner=%s exit=%s timeout=%s duration_ms=%s",
        scanner.name,
        run.exit_code,
        run.timed_out,
        run.duration_ms,
    )
    return run


def evaluate_completeness(
    run: ToolRun,
    *,
    ok_exit_codes: Iterable[int] = (0,),
    requires_output: bool = True,
) -> tuple[bool, str]:
    """Return ``(scan_complete, partial_reason)`` for *run*.

    A run is complete only when the sandbox did not stop it, the tool exited
    with a code documented as "the scan ran to the end" and it produced a
    report.  Anything else is reported as incomplete so that a missing
    absence-proof can never resolve an existing finding.
    """
    if run.timed_out:
        return False, "timeout"
    if run.memory_exceeded:
        return False, "memory_exceeded"
    if run.output_truncated:
        return False, f"output_truncated_at_{run.max_output_bytes}_bytes"
    if run.killed_reason and run.killed_reason not in ("", "exit_code"):
        return False, run.killed_reason
    if run.exit_code not in set(ok_exit_codes):
        return False, f"exit_code_{run.exit_code}"
    if requires_output and not run.stdout.strip() and not run.stderr.strip():
        return False, "empty_output"
    return True, ""


#: Suffixes ``advisory.services.scan_ingestion`` treats as execution
#: diagnostics (never vulnerabilities, never resolution evidence).
_DIAGNOSTIC_SUFFIXES = (
    ".timeout",
    ".memory_exceeded",
    ".incomplete",
    ".output_truncated",
    ".execution_failed",
    ".sandbox_unavailable",
    ".unparsable_report",
)


def incomplete_finding(
    scanner_name: str,
    reason: str,
    *,
    duration_ms: int = 0,
) -> NormalizedFinding:
    """Build the diagnostic finding that explains an incomplete run.

    The suffix is derived from the machine-readable reason so the ingestion
    layer recognises it as an execution diagnostic.  Keeping this finding in
    the outcome is what lets an operator see *why* nothing was resolved; it is
    never a vulnerability and never proves that a finding is gone.
    """
    suffix = "incomplete"
    if reason == "timeout":
        suffix = "timeout"
    elif reason == "memory_exceeded":
        suffix = "memory_exceeded"
    elif reason.startswith("output_truncated"):
        suffix = "output_truncated"
    elif reason == "sandbox_unavailable":
        suffix = "sandbox_unavailable"
    elif reason == "unparsable_report":
        suffix = "unparsable_report"

    return NormalizedFinding(
        check_code=f"{scanner_name}.{suffix}",
        category="security",
        severity=Severity.INFO,
        status=FindingStatus.UNKNOWN,
        title=f"{scanner_name} run incomplete ({reason})",
        description=(
            f"The {scanner_name} run did not complete ({reason}); its report "
            "cannot prove that unchecked findings are gone."
        ),
        duration_ms=duration_ms,
    )


def _has_diagnostic_finding(findings: Sequence[NormalizedFinding]) -> bool:
    return any(
        (finding.check_code or "").endswith(_DIAGNOSTIC_SUFFIXES)
        for finding in findings
    )


def build_outcome(
    scanner: Any,
    *,
    run: ToolRun,
    findings: list[NormalizedFinding],
    message: str,
    status: str = "neutral",
    recommendation: str = "",
    scan_complete: bool = True,
    partial_reason: str = "",
    raw_report: str | None = None,
    raw_report_format: str = "",
    raw_report_meta: dict[str, Any] | None = None,
    **details: Any,
) -> ScanOutcome:
    """Assemble the ``ScanOutcome`` for one tool execution.

    The completeness facts are always part of ``ScanResult.details`` so the
    orchestrator's ``ScannerRun`` records them even when the adapter is used
    outside the orchestrator (legacy public checker).  An incomplete run always
    carries an execution-diagnostic finding, so a caller that only reads the
    findings cannot mistake it for a clean result.
    """
    if not scan_complete:
        reason = partial_reason or "incomplete"
        if not _has_diagnostic_finding(findings):
            findings = [
                *findings,
                incomplete_finding(
                    scanner.name, reason, duration_ms=run.duration_ms
                ),
            ]

    details.setdefault("timed_out", run.timed_out)
    details.setdefault("memory_exceeded", run.memory_exceeded)
    details.setdefault("output_truncated", run.output_truncated)
    details.setdefault("exit_code", run.exit_code)
    details.setdefault("scan_complete", bool(scan_complete))
    details.setdefault("partial_reason", partial_reason)
    details.setdefault("tool_duration_ms", run.duration_ms)
    if run.max_output_bytes:
        details.setdefault("max_output_bytes", run.max_output_bytes)

    result = ScanResult(
        score=None,
        status=status,
        message=message,
        details=details,
        recommendation=recommendation,
        duration_ms=run.duration_ms,
    )
    return ScanOutcome(
        result=result,
        findings=findings,
        raw_report=raw_report,
        raw_report_format=raw_report_format,
        raw_report_meta=dict(raw_report_meta or {}),
    )


def execution_finding(
    scanner_name: str,
    suffix: str,
    title: str,
    *,
    description: str = "",
    severity: str = Severity.INFO,
    duration_ms: int = 0,
) -> NormalizedFinding:
    """Build a non-vulnerability, operational finding for a failed run.

    The ``<scanner>.<suffix>`` codes are recognised by
    ``advisory.services.scan_ingestion`` as execution diagnostics: they never
    create a ``SecurityFinding`` and they force a non-resolving ingest.
    """
    return NormalizedFinding(
        check_code=f"{scanner_name}.{suffix}",
        category="security",
        severity=severity,
        status=FindingStatus.UNKNOWN,
        title=title,
        description=description,
        duration_ms=duration_ms,
    )


def unavailable_outcome(
    scanner: Any,
    *,
    reason: str,
    message: str | None = None,
    raw_report_format: str = "",
) -> ScanOutcome:
    """Outcome for a scanner that could not be started at all."""
    text = message or f"{scanner.name} could not be started: {reason}"
    return build_outcome(
        scanner,
        run=ToolRun(exit_code=-1),
        findings=[
            execution_finding(
                scanner.name,
                "sandbox_unavailable",
                f"{scanner.name} could not run",
                description=reason,
                severity=Severity.MEDIUM,
            )
        ],
        message=text,
        status="warning",
        scan_complete=False,
        partial_reason="sandbox_unavailable",
        unavailable=True,
        raw_report_format=raw_report_format,
    )


def target_validation_outcome(
    scanner: Any,
    *,
    error: str,
    category: str = "security",
) -> ScanOutcome:
    """Outcome for a target rejected by the central SSRF gate."""
    return ScanOutcome(
        result=ScanResult(
            score=None,
            status="critical",
            message=error,
            details={
                "scan_complete": False,
                "partial_reason": "target_validation",
                "timed_out": False,
                "exit_code": -1,
            },
        ),
        findings=[
            NormalizedFinding(
                check_code=f"{scanner.name}.target_validation",
                category=category,
                severity=Severity.HIGH,
                status=FindingStatus.FAIL,
                title="Target validation failed",
                description=error,
            )
        ],
    )


__all__ = [
    "REPORT_READ_LIMIT_BYTES",
    "ToolRun",
    "build_outcome",
    "evaluate_completeness",
    "execution_finding",
    "incomplete_finding",
    "read_report_file",
    "report_workdir",
    "resolve_target",
    "run_tool",
    "target_validation_outcome",
    "unavailable_outcome",
    "SandboxError",
    "TargetValidationError",
]
