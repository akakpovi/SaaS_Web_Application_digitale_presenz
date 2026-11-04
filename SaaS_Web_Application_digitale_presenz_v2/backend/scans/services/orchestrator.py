"""Scan Orchestrator — the core of the Scanner Engine.

Orchestrates the execution of multiple scanners for a given scan, tracking
progress, creating ScannerRun/Finding records, and updating the scan state.

Architecture principles
-----------------------
* One ``ScannerRun`` per scanner per scan.
* Findings are normalised and stored independently of CheckResults.
* CheckResults are still populated for backward compatibility with the
  existing health score engine.
* The orchestrator is scanner-agnostic — it uses the ScannerRegistry.
* A single scanner failure does NOT fail the entire scan.
* Progress is updated in real-time via Scan.steps.

Scan lifecycle
--------------
PENDING → QUEUED (transition handled outside orchestrator, before task dispatch)
QUEUED → RUNNING (orchestrator takes ownership here)
RUNNING → COMPLETED | PARTIAL | FAILED | CANCELLED

Usage::

    orchestrator = ScanOrchestrator(scan_id=42)
    orchestrator.run()
"""

from __future__ import annotations

import inspect
import logging
import time
from typing import Any

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _budget_settings_for_scan(scan: Any) -> tuple[str, int]:
    """Return ``(setting name, default)`` for the scan's wall-clock budget.

    Each journey stage has its own envelope: 150 s for the bounded TLS stage
    and 360 s for the scenario-C stage.  ``journey_stage=None`` (every classic
    monitoring scan) keeps the historical 540-second budget.
    """
    stage = getattr(scan, "journey_stage", None)
    if stage == 1:
        return "SCAN_JOURNEY_STAGE1_TIME_BUDGET_SECONDS", 150
    if stage == 2:
        return "SCAN_JOURNEY_STAGE2_TIME_BUDGET_SECONDS", 360
    return "SCAN_TOTAL_TIME_BUDGET_SECONDS", 540


def claim_scan(scan_id: int) -> bool:
    """Atomically move a scan from QUEUED to RUNNING.

    A single conditional ``UPDATE`` is the whole claim: two workers (or two
    deliveries of the same Celery message) cannot both succeed, because the
    second one no longer matches ``status='queued'``.  This is deliberately
    not ``select_for_update()`` + ``save()``: that pattern can still let a
    stale in-memory row overwrite the transition of another worker.

    Returns:
        True when this caller owns the scan, False when it was already claimed
        (RUNNING) or is no longer queued (terminal/cancelled).
    """
    from scans.models import Scan

    now = timezone.now()
    updated = Scan.objects.filter(
        id=scan_id,
        status=Scan.Status.QUEUED,
    ).update(
        status=Scan.Status.RUNNING,
        started_at=now,
        # ``auto_now`` is bypassed by ``QuerySet.update()``; the reaper relies
        # on ``updated_at`` to measure idleness, so set it explicitly.
        updated_at=now,
    )
    return updated == 1


class ScanOrchestrator:
    """Orchestrates scanner execution for a given scan."""

    #: Memoised answer to "does this scanner accept ``scan_findings(result=…)``?".
    #: Internal scanners inherit it from ``BaseScanner``; the CLI adapters
    #: manage their own execution lifecycle and only accept ``domain``.
    _FINDINGS_ACCEPTS_RESULT: dict[type, bool] = {}

    def __init__(self, scan_id: int) -> None:
        self.scan_id = scan_id
        # Wall-clock deadline shared by every step of this scan.
        self._deadline: float = time.monotonic()
        # Central SSRF validation, computed once per scan and reused for every
        # external tool. ``_target_error`` memoises a rejection so later
        # external steps fail fast without re-resolving DNS.
        self._target_info: Any | None = None
        self._target_error: str | None = None
        # Wall-clock budget of the active scan (540 s classic, 360 s stage 2).
        self._time_budget_seconds: int = 540
        # Stage-2 cross-scanner de-duplication (Nuclei content proof vs a
        # Gobuster path discovery).  Disabled for classic scans so their
        # historical finding set is preserved exactly.
        self._dedup_findings: bool = False
        self._finding_keys: set[tuple[str, str, str]] = set()
        self._findings_by_key: dict[tuple[str, str, str], Any] = {}
        self._findings_by_path: dict[str, Any] = {}

    @classmethod
    def _findings_accepts_result(cls, scanner: Any) -> bool:
        """Return True when ``scanner.scan_findings`` accepts ``result=``."""
        key = type(scanner)
        if key not in cls._FINDINGS_ACCEPTS_RESULT:
            try:
                params = inspect.signature(scanner.scan_findings).parameters
                cls._FINDINGS_ACCEPTS_RESULT[key] = "result" in params
            except (TypeError, ValueError):
                cls._FINDINGS_ACCEPTS_RESULT[key] = False
        return cls._FINDINGS_ACCEPTS_RESULT[key]

    def _collect_findings(self, scanner: Any, domain: str, scan_result: Any) -> list:
        """Derive findings from an already-computed ScanResult.

        The scanner is never executed a second time: the orchestrator has
        already called ``scan()``.  Reusing its result halves the outbound
        traffic per scan and guarantees findings match the persisted
        CheckResult.
        """
        if self._findings_accepts_result(scanner):
            return scanner.scan_findings(domain, result=scan_result)
        return scanner.scan_findings(domain)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Execute the full scan lifecycle.

        Called by the Celery task.  Exceptions that escape this method are
        caught by the Celery task itself and result in the scan being marked
        FAILED.
        """
        from scans.models import Scan
        from scans.services.scoring import recalculate_scan_health
        from scans.services.status import aggregate_scan_status
        from scans.services.steps_builder import get_steps_for_scan

        scan = self._load_scan()
        if scan is None:
            return

        # Idempotency guard: don't re-run a terminal scan.  PARTIAL is final:
        # a retry must never turn a timeout into a success.
        if scan.status in (
            Scan.Status.COMPLETED,
            Scan.Status.PARTIAL,
            Scan.Status.FAILED,
            Scan.Status.CANCELLED,
        ):
            logger.info(
                "ScanOrchestrator: Scan %d is already %s — skipping",
                self.scan_id,
                scan.status,
            )
            return

        domain = scan.website.domain

        # Only journey stage 2 opts into cross-scanner de-duplication.
        self._dedup_findings = scan.journey_stage == 2
        self._finding_keys.clear()
        self._findings_by_key.clear()
        self._findings_by_path.clear()

        # Hard budget for the whole scan (all steps share it). A slow external
        # tool must never keep a Celery worker busy beyond this deadline.
        # Journey stage 2 has its own 360 s envelope; every other scan keeps
        # the historical 540 s budget, including classic monitoring scans.
        budget_setting, default_budget = _budget_settings_for_scan(scan)
        budget = max(1, int(getattr(settings, budget_setting, default_budget)))
        self._time_budget_seconds = budget
        self._deadline = time.monotonic() + budget

        # Initialise steps for this scan.  ``journey_stage=2`` selects the
        # scenario-C pipeline; classic scans keep the historical lists.
        steps = get_steps_for_scan(scan)
        scan.steps = steps
        scan.progress = 0
        scan.current_step = ""
        scan.save(update_fields=["steps", "progress", "current_step", "updated_at"])

        # QUEUED → RUNNING
        try:
            scan.transition_to(Scan.Status.RUNNING)
        except Exception as exc:
            logger.error(
                "ScanOrchestrator: Cannot transition scan %d to RUNNING: %s",
                self.scan_id,
                exc,
            )
            return

        # ── Run all scanner steps ──────────────────────────────────────
        try:
            self._run_all_steps(scan, domain, steps)
        except Exception as exc:
            logger.exception(
                "ScanOrchestrator: Unexpected error for scan %d", self.scan_id
            )
            try:
                scan.transition_to(Scan.Status.FAILED, failure_message=str(exc)[:500])
            except Exception:
                pass
            return

        # ── Check if cancelled during steps ────────────────────────────
        scan.refresh_from_db(fields=["status"])
        if scan.status == Scan.Status.CANCELLED:
            logger.info("ScanOrchestrator: Scan %d cancelled. Stopping.", self.scan_id)
            return

        # ── Recalculate health score ───────────────────────────────────
        # A journey stage is not a full-site measurement: stage 1 only proves
        # TLS and stage 2 only covers Nuclei/Gobuster.  Writing a scan-level
        # health score for such a stage would present a partial measurement as
        # the site's health, so journey children keep ``health_score=NULL``.
        # Classic scans keep the historical recalculation untouched.
        if scan.journey_id is None:
            try:
                recalculate_scan_health(scan)
            except Exception as exc:
                logger.error(
                    "ScanOrchestrator: Failed to recalculate health for scan "
                    "%d: %s",
                    self.scan_id,
                    exc,
                )

        # ── Finalise from the stored per-scanner outcomes ─────────────
        # ``Scan.status`` must describe what was actually verified, not just
        # that the loop returned.  A timeout/failed/unavailable required step
        # downgrades the scan to PARTIAL (or FAILED when nothing usable was
        # produced).
        scan.progress = 100
        scan.current_step = ""
        summary = aggregate_scan_status(scan.steps)
        if summary.status == Scan.Status.PARTIAL:
            scan.failure_message = summary.reason[:500]
            scan.save(
                update_fields=[
                    "failure_message",
                    "progress",
                    "current_step",
                    "updated_at",
                ]
            )
            scan.transition_to(Scan.Status.PARTIAL)
        elif summary.status == Scan.Status.FAILED:
            scan.transition_to(
                Scan.Status.FAILED,
                failure_message=summary.reason,
            )
        else:
            scan.save(update_fields=["progress", "current_step", "updated_at"])
            scan.transition_to(Scan.Status.COMPLETED)
        logger.info(
            "ScanOrchestrator: Scan %d finished with status=%s (completed=%s, "
            "incomplete=%s)",
            self.scan_id,
            summary.status,
            ",".join(summary.completed) or "-",
            ",".join(summary.incomplete) or "-",
        )

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    def _run_all_steps(
        self,
        scan: Any,
        domain: str,
        steps: list[dict[str, Any]],
    ) -> None:
        """Iterate through all steps, running each scanner in order.

        The orchestrator is the policy layer for delegated tools:

        * every external scanner receives an SSRF-validated target computed
          centrally by :meth:`_validated_target`;
        * every step's timeout is clamped by the remaining scan budget and by
          ``SCANNER_SANDBOX['max_timeout']``;
        * the executor inside the adapter enforces CPU/RAM/process limits.
        """
        from scanners.base import ScanContext, ScannerType
        from scanners.features import advanced_security_enabled
        from scanners.registry import ScannerRegistry
        from scans.models import Scan
        from scans.services.steps_builder import compute_overall_progress, StepStatus

        for index, step in enumerate(steps):
            key = step["key"]
            scanner_name = step["scanner"]

            # ── Check for cancellation before every step ───────────────
            scan.refresh_from_db(fields=["status"])
            if scan.status == Scan.Status.CANCELLED:
                logger.info(
                    "ScanOrchestrator: Scan %d was cancelled — stopping at step '%s'",
                    self.scan_id,
                    key,
                )
                # Mark remaining pending steps as cancelled.
                for remaining in steps:
                    if remaining.get("status") == StepStatus.PENDING:
                        remaining["status"] = StepStatus.SKIPPED
                scan.steps = steps
                scan.save(update_fields=["steps", "updated_at"])
                return

            # ── Enforce the overall wall-clock budget ──────────────────
            if self._remaining_seconds() <= 0:
                self._skip_from(
                    steps,
                    index,
                    "Scan time budget exhausted "
                    f"({self._time_budget_seconds}s)",
                )
                self._flush_step(scan, steps)
                logger.warning(
                    "ScanOrchestrator: Scan %d exhausted its time budget at step '%s'",
                    self.scan_id,
                    key,
                )
                return

            # ── Mark step as running ───────────────────────────────────
            step["status"] = StepStatus.RUNNING
            step["progress"] = 0
            scan.current_step = step["label"]
            scan.steps = steps
            scan.progress = compute_overall_progress(steps)
            scan.save(update_fields=["steps", "current_step", "progress", "updated_at"])

            # ── Resolve scanner from registry ──────────────────────────
            try:
                scanner = ScannerRegistry.get(scanner_name)
            except KeyError:
                logger.warning(
                    "ScanOrchestrator: Scanner '%s' not in registry — skipping step '%s'",
                    scanner_name,
                    key,
                )
                step["status"] = StepStatus.SKIPPED
                step["progress"] = 100
                step["error"] = f"Scanner '{scanner_name}' not registered"
                self._flush_step(scan, steps)
                continue

            # ── Advanced security tier gate ────────────────────────────
            # ZAP/Nuclei send attack payloads and are opt-in only.  Refuse
            # before creating a ScannerRun or resolving any target.
            if (
                getattr(scanner, "requires_advanced_security", False) is True
                and not advanced_security_enabled()
            ):
                logger.info(
                    "ScanOrchestrator: skipping advanced scanner '%s' for scan "
                    "%d (SCANNER_ADVANCED_SECURITY_ENABLED=false)",
                    scanner_name,
                    self.scan_id,
                )
                step["status"] = StepStatus.SKIPPED
                step["progress"] = 100
                # The deployment policy explicitly excluded this scanner: it
                # is optional for this scan, not a failed required check.
                step["required"] = False
                step["error"] = (
                    "Advanced security scanner disabled "
                    "(SCANNER_ADVANCED_SECURITY_ENABLED=false)"
                )
                self._flush_step(scan, steps)
                continue

            # ── Run the scanner ────────────────────────────────────────
            step_start = time.monotonic()
            scanner_run = self._create_scanner_run(scan, scanner_name)
            scanner_run.start()

            # Only string constants qualify: test doubles and third-party
            # adapters without ``scanner_type`` are treated as internal.  The
            # coerced value is also what gets persisted in ScannerRun.metadata
            # (JSONField), so it must never be an arbitrary object.
            scanner_type = getattr(scanner, "scanner_type", ScannerType.INTERNAL)
            if not isinstance(scanner_type, str):
                scanner_type = ScannerType.INTERNAL
            is_external = scanner_type in (
                ScannerType.CLI,
                ScannerType.API,
            )
            target = None
            effective_timeout = 0
            sandbox_limits = None

            try:
                step["progress"] = 10
                self._flush_step(scan, steps)

                # Check availability (external tools may not be installed).
                # Do this BEFORE DNS resolution: an absent binary must not
                # trigger unnecessary lookups.
                if not scanner.is_available():
                    raise ScannerUnavailable(
                        f"Scanner '{scanner_name}' binary not found on PATH"
                    )

                effective_timeout = self._effective_timeout(
                    scanner, scanner_name, step=step
                )

                # ── Central SSRF gate for every delegated tool ─────────
                if is_external:
                    from scanners.executors.sandbox import get_sandbox_executor

                    target = self._validated_target(domain)
                    # The orchestrator owns the resource envelope; adapters
                    # consume it instead of re-deriving their own limits.
                    sandbox_limits = get_sandbox_executor().limits_for(
                        scanner_name, timeout=effective_timeout
                    )
                    logger.info(
                        "ScanOrchestrator: delegating '%s' to SSRF-validated "
                        "target %s (ips=%d, timeout=%ds, mem=%dMB)",
                        scanner_name,
                        target.hostname,
                        len(target.safe_ips),
                        effective_timeout,
                        sandbox_limits.memory_mb,
                    )

                context = ScanContext(
                    scan_id=self.scan_id,
                    domain=domain,
                    timeout=effective_timeout,
                    deadline_monotonic=self._deadline,
                    target=target,
                    sandbox_limits=sandbox_limits,
                    # Trusted step definition: the orchestrator, never request
                    # data, selects the Nuclei profile for stage-2 journeys.
                    profile=step.get("profile"),
                )

                # Run the scanner ONCE via ``execute()``.  Adapters that
                # override it (Lighthouse, testssl.sh) return the ScanResult
                # and the findings derived from the same raw output; legacy
                # adapters fall back to scan() + scan_findings().
                outcome = self._execute_scanner(scanner, context)
                scan_result = outcome.result
                findings = outcome.findings
                step["progress"] = 80

                # Archive the raw report before any normalisation is used for
                # resolution.  A storage failure is recorded, not raised.
                archive_metadata = self._archive_scanner_report(
                    scanner_run, scan, scanner_name, outcome
                )

                # Persist findings to DB.
                self._persist_findings(scanner_run, findings)

                # Feed the vulnerability scanners into the long-lived, tenant
                # scoped SecurityFinding table the AI advisor reads.  A partial
                # run is ingested without resolving anything.
                self._ingest_security_findings(
                    scan, scanner_name, findings, scan_result
                )

                # Persist CheckResult (backward compat with health score engine).
                self._persist_check_result(scan, scanner, scan_result)
                # The result was persisted, so it is usable even when the
                # scanner later reports an incomplete run (timeout/partial).
                step["result_usable"] = True

                from scans.models import ScannerRun

                duration_ms = int((time.monotonic() - step_start) * 1000)
                details = scan_result.details or {}
                timed_out = bool(details.get("timed_out"))
                scan_complete = details.get("scan_complete")
                if scan_complete is None:
                    # Legacy adapters do not report completeness: keep the
                    # previous behaviour (only an explicit timeout disables
                    # resolution).
                    scan_complete = not (
                        timed_out or details.get("memory_exceeded")
                    )
                if timed_out:
                    run_status = ScannerRun.Status.TIMEOUT
                elif not scan_complete:
                    run_status = ScannerRun.Status.PARTIAL
                else:
                    run_status = ScannerRun.Status.COMPLETED
                run_metadata = {
                        "findings_count": len(findings),
                        "scanner_status": scan_result.status,
                        "score": scan_result.score,
                        "scanner_type": scanner_type,
                        "timeout_s": effective_timeout,
                        "target_validated": target is not None,
                        "memory_mb": getattr(sandbox_limits, "memory_mb", None),
                        "cpu_seconds": getattr(sandbox_limits, "cpu_seconds", None),
                        "scan_complete": bool(scan_complete),
                        "partial_reason": details.get("partial_reason", ""),
                        "output_truncated": details.get("output_truncated"),
                        "profile": details.get("profile"),
                        "profile_timeout_s": details.get("profile_timeout_s"),
                        "duration_alert_s": details.get("duration_alert_s"),
                        "duration_over_alert": details.get(
                            "duration_over_alert"
                        ),
                        "templates_loaded": details.get("templates_loaded"),
                        "percent": details.get("percent"),
                        "requests": details.get("requests"),
                        "errors": details.get("errors"),
                        "host_skipped": details.get("host_skipped"),
                    }
                if archive_metadata:
                    run_metadata["archive"] = archive_metadata
                scanner_run.finish(
                    status=run_status,
                    # Diagnostics required to audit a run afterwards: exit
                    # code, profile, progress and Nuclei request counters.
                    exit_code=details.get("exit_code"),
                    metadata=run_metadata,
                    duration_ms=duration_ms,
                )
                if details.get("duration_over_alert"):
                    logger.warning(
                        "ScanOrchestrator: scanner '%s' exceeded its %ss "
                        "alert threshold for scan %d (duration=%dms)",
                        scanner_name,
                        details.get("duration_alert_s"),
                        self.scan_id,
                        duration_ms,
                    )
                step["status"] = (
                    StepStatus.TIMEOUT
                    if run_status == ScannerRun.Status.TIMEOUT
                    else StepStatus.PARTIAL
                    if run_status == ScannerRun.Status.PARTIAL
                    else StepStatus.COMPLETED
                )
                step["progress"] = 100
                step["duration_ms"] = duration_ms
                step["error"] = (
                    str(details.get("partial_reason") or "")[:500]
                    if step["status"] != StepStatus.COMPLETED
                    else None
                )

            except ScannerBlocked as exc:
                # A rejected target is a *security* outcome, distinct from a
                # tool failure.  No data was collected: the scanner was never
                # invoked.  The remaining (internal) steps still run.
                duration_ms = int((time.monotonic() - step_start) * 1000)
                logger.warning(
                    "ScanOrchestrator: SSRF gate blocked scanner '%s' for scan "
                    "%d (%s)",
                    scanner_name,
                    self.scan_id,
                    exc,
                )
                scanner_run.finish(
                    status="failed",
                    error_message=str(exc)[:500],
                    metadata={
                        "blocked": True,
                        "reason": "ssrf",
                        "scanner_type": scanner_type,
                        "timeout_s": effective_timeout,
                        "target_validated": False,
                        "memory_mb": getattr(sandbox_limits, "memory_mb", None),
                        "cpu_seconds": getattr(sandbox_limits, "cpu_seconds", None),
                    },
                    duration_ms=duration_ms,
                )
                step["status"] = StepStatus.FAILED
                step["progress"] = 100
                step["duration_ms"] = duration_ms
                step["error"] = str(exc)[:500]

            except ScannerUnavailable as exc:
                duration_ms = int((time.monotonic() - step_start) * 1000)
                logger.info(
                    "ScanOrchestrator: Scanner '%s' unavailable for scan %d: %s",
                    scanner_name,
                    self.scan_id,
                    exc,
                )
                scanner_run.finish(
                    status="unavailable",
                    error_message=str(exc)[:500],
                    metadata={
                        "scanner_type": scanner_type,
                        "timeout_s": effective_timeout,
                        "memory_mb": getattr(sandbox_limits, "memory_mb", None),
                        "cpu_seconds": getattr(sandbox_limits, "cpu_seconds", None),
                    },
                    duration_ms=duration_ms,
                )
                step["status"] = StepStatus.UNAVAILABLE
                step["progress"] = 100
                step["duration_ms"] = duration_ms
                step["error"] = str(exc)
                # Not an error — gracefully continue.

            except Exception as exc:
                duration_ms = int((time.monotonic() - step_start) * 1000)
                error_msg = str(exc)[:500]
                logger.exception(
                    "ScanOrchestrator: Scanner '%s' failed for scan %d: %s",
                    scanner_name,
                    self.scan_id,
                    error_msg,
                )
                scanner_run.finish(
                    status="failed",
                    error_message=error_msg,
                    metadata={
                        "scanner_type": scanner_type,
                        "timeout_s": effective_timeout,
                        "memory_mb": getattr(sandbox_limits, "memory_mb", None),
                        "cpu_seconds": getattr(sandbox_limits, "cpu_seconds", None),
                    },
                    duration_ms=duration_ms,
                )
                step["status"] = StepStatus.FAILED
                step["progress"] = 100
                step["duration_ms"] = duration_ms
                step["error"] = error_msg
                # Do NOT re-raise — one scanner failure should not abort the scan.

            self._flush_step(scan, steps)

    # ------------------------------------------------------------------
    # Delegation helpers
    # ------------------------------------------------------------------

    def _remaining_seconds(self) -> float:
        """Seconds left in the overall scan budget."""
        return max(0.0, self._deadline - time.monotonic())

    @staticmethod
    def _skip_from(
        steps: list[dict[str, Any]],
        start_index: int,
        reason: str,
    ) -> None:
        """Mark a step and every later pending step as skipped."""
        from scans.services.steps_builder import StepStatus

        for step in steps[start_index:]:
            if step.get("status") == StepStatus.PENDING:
                step["status"] = StepStatus.SKIPPED
                step["error"] = reason

    def _effective_timeout(
        self,
        scanner: Any,
        scanner_name: str,
        *,
        step: dict[str, Any] | None = None,
    ) -> int:
        """Clamp the scanner timeout to the sandbox cap and scan budget.

        A stage-2 step may name a ``timeout_setting``; that deployment setting
        is then authoritative (180 s Nuclei, 120 s Gobuster).  Otherwise the
        historical precedence applies: an adapter's ``profile_timeout``
        (Nuclei) wins over ``SCANNER_CONFIG[name]["timeout"]``.
        """
        scanner_cfg = self._scanner_cfg(scanner_name)
        try:
            configured = int(scanner_cfg.get("timeout", scanner.timeout))
        except (TypeError, ValueError):
            # A malformed third-party adapter must not crash the whole step.
            configured = 60

        step_timeout: int | None = None
        if step:
            setting_name = step.get("timeout_setting")
            if setting_name:
                try:
                    step_timeout = max(1, int(getattr(settings, setting_name)))
                except (AttributeError, TypeError, ValueError):
                    step_timeout = None
        if step_timeout is not None:
            configured = step_timeout
        else:
            profile_timeout = getattr(scanner, "profile_timeout", None)
            # Only a real integer is authoritative.  MagicMock-based test
            # doubles (and third-party adapters) return arbitrary objects
            # whose int() is meaningless and must keep the legacy fallback.
            if isinstance(profile_timeout, int) and not isinstance(
                profile_timeout, bool
            ):
                configured = profile_timeout

        sandbox_cfg = getattr(settings, "SCANNER_SANDBOX", {}) or {}
        max_timeout = int(sandbox_cfg.get("max_timeout", 300) or 300)
        remaining = int(self._remaining_seconds())

        if configured > max_timeout:
            logger.warning(
                "ScanOrchestrator: '%s' profile budget %ds exceeds sandbox "
                "max_timeout %ds; the effective budget is clamped",
                scanner_name,
                configured,
                max_timeout,
            )

        # ``remaining`` is 0 when less than one second is left: the caller
        # has already checked the budget, so one second is the floor.
        return max(1, min(configured, max_timeout, remaining or 1))

    def _validated_target(self, domain: str) -> Any:
        """Return the centrally validated target for external tools.

        This is the single SSRF entry point for delegation.  It blocks
        localhost, private/link-local ranges and cloud metadata endpoints by
        delegating to :mod:`core.security` (via the scanner adapter), and it
        memoises both success and rejection for the whole scan.

        Raises:
            ScannerBlocked: when the target is not a public, resolvable host.
        """
        from scanners.exceptions import TargetValidationError
        from scanners.security.target_validator import validate_target

        if self._target_error is not None:
            raise ScannerBlocked(self._target_error)
        if self._target_info is not None:
            return self._target_info

        try:
            target = validate_target(f"https://{domain}")
        except TargetValidationError as exc:
            self._target_error = f"Target blocked by SSRF protection: {exc}"
            logger.warning(
                "ScanOrchestrator: central SSRF validation rejected %r for "
                "scan %d: %s",
                domain,
                self.scan_id,
                exc,
            )
            raise ScannerBlocked(self._target_error) from exc

        self._target_info = target
        return target

    def _execute_scanner(self, scanner: Any, context: Any) -> Any:
        """Execute a scanner exactly once and return a ``ScanOutcome``.

        Scanners implementing ``execute(domain, context=…)`` (Lighthouse,
        testssl.sh) return a :class:`~scanners.base.ScanOutcome` carrying both
        halves of the run.  Legacy adapters fall back to
        ``scan()`` + ``scan_findings()``.
        """
        from scanners.base import ScanOutcome

        execute = getattr(scanner, "execute", None)
        if callable(execute):
            try:
                params = inspect.signature(execute).parameters
                accepts_context = "context" in params or any(
                    param.kind is inspect.Parameter.VAR_KEYWORD
                    for param in params.values()
                )
            except (TypeError, ValueError):
                accepts_context = False

            outcome = (
                execute(context.domain, context=context)
                if accepts_context
                else execute(context.domain)
            )
            if isinstance(outcome, ScanOutcome):
                return outcome

            logger.debug(
                "ScanOrchestrator: scanner '%s' execute() returned %s — "
                "falling back to scan()/scan_findings()",
                getattr(scanner, "name", "?"),
                type(outcome).__name__,
            )

        scan_result = scanner.scan(context.domain)
        return ScanOutcome(
            result=scan_result,
            findings=self._collect_findings(
                scanner, context.domain, scan_result
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_scan(self) -> Any | None:
        from scans.models import Scan

        try:
            return Scan.objects.select_related("website").get(pk=self.scan_id)
        except Scan.DoesNotExist:
            logger.error(
                "ScanOrchestrator: Scan %d not found", self.scan_id
            )
            return None

    def _scanner_cfg(self, name: str) -> dict:
        """Return per-scanner settings from SCANNER_CONFIG."""
        return getattr(settings, "SCANNER_CONFIG", {}).get(name, {})

    def _flush_step(self, scan: Any, steps: list[dict]) -> None:
        """Persist step progress and recompute overall progress."""
        from scans.services.steps_builder import compute_overall_progress

        scan.steps = steps
        scan.progress = compute_overall_progress(steps)
        scan.save(update_fields=["steps", "progress", "updated_at"])

    def _create_scanner_run(self, scan: Any, scanner_name: str) -> Any:
        from scans.models import ScannerRun

        return ScannerRun.objects.create(
            scan=scan,
            scanner=scanner_name,
            status=ScannerRun.Status.PENDING,
        )

    def _ingest_security_findings(
        self,
        scan: Any,
        scanner_name: str,
        findings: list,
        scan_result: Any,
    ) -> None:
        """Ingest ZAP/Nuclei results into ``SecurityFinding``, never failing.

        The scan and its raw findings are already persisted at this point, so
        an ingestion problem is logged and swallowed: a broken advisor table
        must not turn a successful scan into a failed one.

        ``complete`` is false when the sandbox stopped the tool (timeout or
        memory limit): the partial report cannot prove that the findings it
        does not mention are gone.
        """
        try:
            from advisory.services.scan_ingestion import ingest_scan_findings

            details = getattr(scan_result, "details", None) or {}
            complete = details.get("scan_complete")
            if complete is None:
                complete = not bool(
                    details.get("timed_out") or details.get("memory_exceeded")
                )
            # A complete run only proves that findings *inside its coverage*
            # are gone.  A narrower profile (Nuclei standard: no info/low, no
            # default-login/fuzzing) must never close out-of-scope findings.
            allow_resolution = bool(details.get("resolve_missing", True))
            complete = bool(complete and allow_resolution)
            outcome = ingest_scan_findings(
                scan=scan,
                scanner_name=scanner_name,
                findings=findings,
                complete=complete,
            )
            if outcome is not None:
                logger.info(
                    "ScanOrchestrator: ingested %s findings for scan %d "
                    "(created=%d updated=%d resolved=%d complete=%s)",
                    scanner_name,
                    self.scan_id,
                    outcome.created,
                    outcome.updated,
                    outcome.resolved,
                    complete,
                )
        except Exception:
            logger.exception(
                "ScanOrchestrator: ingestion of '%s' failed for scan %d — "
                "scan results are kept, SecurityFinding rows may be stale",
                scanner_name,
                self.scan_id,
            )

    def _archive_scanner_report(
        self,
        scanner_run: Any,
        scan: Any,
        scanner_name: str,
        outcome: Any,
    ) -> dict[str, Any]:
        """Privately archive a raw report; never fail or shorten ingestion.

        Only scanners selected by ``SCANNER_ARCHIVE_SCANNERS`` are archived
        (Nuclei by default).  The archive is best-effort and its status is
        returned so ``ScannerRun.metadata`` can make a storage failure
        explicit.  Ingestion runs regardless: a missing archive must not be
        mistaken for a missing report.
        """
        configured = getattr(
            settings, "SCANNER_ARCHIVE_SCANNERS", ("nuclei",)
        )
        if scanner_name not in tuple(configured or ()):
            return {}

        details = getattr(getattr(outcome, "result", None), "details", None) or {}
        complete = details.get("scan_complete")
        if complete is None:
            complete = not bool(
                details.get("timed_out") or details.get("memory_exceeded")
            )

        try:
            from scanners.artifacts import archive_report

            result = archive_report(
                scanner_name=scanner_name,
                scan_id=getattr(scan, "pk", None),
                scanner_run_id=getattr(scanner_run, "pk", None),
                raw_report=getattr(outcome, "raw_report", None),
                report_format=(
                    getattr(outcome, "raw_report_format", "") or "jsonl"
                ),
                diagnostics=getattr(outcome, "raw_report_meta", None) or {},
                complete=bool(complete),
                partial_reason=str(details.get("partial_reason") or ""),
            )
            return result.as_metadata()
        except Exception as exc:  # pragma: no cover - service catches its own
            logger.exception(
                "ScanOrchestrator: archive of '%s' failed for scan %d — "
                "scan results are kept and ingestion continues",
                scanner_name,
                self.scan_id,
            )
            return {"status": "failed", "detail": type(exc).__name__}

    def _persist_findings(self, scanner_run: Any, findings: list) -> None:
        """Create Finding records from NormalizedFinding instances.

        Classic scans keep the historical bulk-create behaviour.  Journey
        stage 2 de-duplicates content findings by their canonical identity and
        folds a Gobuster path discovery into the content finding that already
        proved the same resource, so one issue is reported once.
        """
        from scans.models import Finding
        from scans.services.finding_dedup import (
            finding_dedup_key,
            finding_path,
            finding_url,
            is_path_discovery,
            merge_complementary_evidence,
            severity_rank,
        )

        if not findings:
            return

        finding_objs = []
        pending: list[tuple[Any, Any]] = []
        for f in findings:
            # Coerce reference_url to a safe value (no None, not too long).
            ref_url = (f.reference_url or "")[:500]
            content_key: tuple[str, str, str] | None = None

            if self._dedup_findings:
                if is_path_discovery(f):
                    path = finding_path(f)
                    target = self._findings_by_path.get(path) if path else None
                    if target is not None:
                        if merge_complementary_evidence(target, f):
                            if target.pk:
                                target.save(update_fields=["evidence"])
                        logger.debug(
                            "ScanOrchestrator: folded %s into %s (scan %d)",
                            f.check_code,
                            target.check_code,
                            self.scan_id,
                        )
                        continue
                else:
                    url = finding_url(f)
                    if url:
                        content_key = finding_dedup_key(
                            f.category, f.check_code, url
                        )
                        if content_key in self._finding_keys:
                            # Same source, same canonical identity: keep the
                            # highest severity rather than the first seen.
                            existing = self._findings_by_key.get(content_key)
                            if existing is not None and (
                                severity_rank(f.severity)
                                > severity_rank(existing.severity)
                            ):
                                existing.severity = f.severity
                                existing.status = f.status
                                existing.save(
                                    update_fields=["severity", "status"]
                                )
                            continue
                        self._finding_keys.add(content_key)

            obj = Finding(
                scanner_run=scanner_run,
                category=f.category[:32],
                check_code=f.check_code[:128],
                title=f.title[:255],
                description=f.description or "",
                severity=f.severity,
                status=f.status,
                evidence=f.evidence if isinstance(f.evidence, dict) else {},
                detected_value=f.detected_value,
                expected_value=f.expected_value,
                recommendation=f.recommendation or "",
                reference_url=ref_url,
                duration_ms=f.duration_ms if f.duration_ms else None,
            )
            if self._dedup_findings:
                # Individual inserts give each content finding a primary key
                # immediately, so a later Gobuster step can append evidence to
                # the stored row without a second lookup.
                obj.save()
                if content_key is not None:
                    self._findings_by_key[content_key] = obj
                pending.append((f, obj))
            else:
                finding_objs.append(obj)

        if not self._dedup_findings:
            Finding.objects.bulk_create(finding_objs, ignore_conflicts=True)
            logger.debug(
                "ScanOrchestrator: Persisted %d finding(s) for scanner_run %d",
                len(finding_objs),
                scanner_run.pk,
            )
            return

        for f, obj in pending:
            if is_path_discovery(f):
                continue
            path = finding_path(f)
            if path:
                # First content proof wins; a second proof for the same path
                # is a different issue and was already kept under its own key.
                self._findings_by_path.setdefault(path, obj)
        logger.debug(
            "ScanOrchestrator: Persisted %d finding(s) for scanner_run %d "
            "(stage-2 de-duplication)",
            len(pending),
            scanner_run.pk,
        )

    def _persist_check_result(
        self, scan: Any, scanner: Any, scan_result: Any
    ) -> None:
        """Create/update a CheckResult from a ScanResult.

        This bridge keeps the existing health score engine working with the
        new scanner pipeline.  External security scanners (nmap, nikto, etc.)
        do NOT map to CheckResult categories and are ignored here (with a
        warning).

        When several tools measure the same category (e.g. the legacy
        ``performance`` scanner and Lighthouse), the last successful one wins
        and the previous measurement is preserved under
        ``technical_details['previous_measurement']`` for traceability.
        """
        from scans.models import CheckResult

        scanner_name = getattr(scanner, "name", "unknown")

        # Map scanner name → CheckResult category (legacy adapters).
        _CATEGORY_MAP: dict[str, str] = {
            "website":          CheckResult.Category.WEBSITE,
            "ssl":              CheckResult.Category.SSL,
            "dns":              CheckResult.Category.DNS,
            "email_security":   CheckResult.Category.EMAIL_SECURITY,
            "security_headers": CheckResult.Category.SECURITY_HEADERS,
            "performance":      CheckResult.Category.PERFORMANCE,
            "lighthouse":       CheckResult.Category.PERFORMANCE,
            "uptime":           CheckResult.Category.UPTIME,
            "zap":              CheckResult.Category.ZAP,
            "nuclei":           CheckResult.Category.NUCLEI,
        }

        declared = getattr(scanner, "check_result_category", None)
        if isinstance(declared, str) and declared:
            if declared in CheckResult.Category.values:
                category = declared
            else:
                logger.warning(
                    "ScanOrchestrator: scanner '%s' declares unknown "
                    "CheckResult category %r — falling back to name mapping",
                    scanner_name,
                    declared,
                )
                category = _CATEGORY_MAP.get(scanner_name)
        else:
            category = _CATEGORY_MAP.get(scanner_name)

        if category is None:
            # External scanners (nmap, nikto, etc.) do not map onto a
            # CheckResult category.  Log it explicitly: a scanner silently
            # contributing nothing to the health score is a defect, not a
            # normal case.
            logger.warning(
                "ScanOrchestrator: scanner '%s' has no CheckResult category "
                "mapping — no CheckResult persisted for scan %d",
                scanner_name,
                self.scan_id,
            )
            return

        # Uptime and external security results are not part of the weighted
        # health score (monitoring/security data only, reported separately).
        from scans.services.scoring import CHECK_WEIGHTS

        is_unweighted = category not in CHECK_WEIGHTS
        if is_unweighted:
            score = None
        else:
            score = scan_result.score
            if score is None:
                # A weighted category MUST carry a numeric score, otherwise
                # the global health score silently degrades to NULL.
                logger.error(
                    "ScanOrchestrator: scanner '%s' returned score=None for "
                    "weighted category '%s' (scan %d) — coercing to 0",
                    scanner_name,
                    category,
                    self.scan_id,
                )
                score = 0

        details = dict(scan_result.details or {})
        # Provenance: AKA IA must be able to tell which tool produced a value.
        details.setdefault("scanner", scanner_name)

        try:
            existing = CheckResult.objects.filter(
                scan=scan, category=category
            ).first()
            if existing is not None:
                details.setdefault(
                    "previous_measurement",
                    {
                        "summary": (existing.summary or "")[:500],
                        "score": existing.score,
                        "status": existing.status,
                    },
                )

            CheckResult.objects.update_or_create(
                scan=scan,
                category=category,
                defaults={
                    "status": scan_result.status,
                    "score": score,
                    "summary": (scan_result.message or "")[:2000],
                    "recommendation": (scan_result.recommendation or "")[:2000],
                    "technical_details": details,
                },
            )
        except Exception as exc:
            logger.error(
                "ScanOrchestrator: Failed to persist CheckResult for %s: %s",
                scanner_name,
                exc,
            )


class ScannerUnavailable(Exception):
    """Raised when a scanner's binary is not installed."""


class ScannerBlocked(Exception):
    """Raised when the central SSRF gate rejects a scan target.

    The scanner is never invoked; the step is recorded as failed with
    ``metadata={'blocked': True, 'reason': 'ssrf'}``.
    """
