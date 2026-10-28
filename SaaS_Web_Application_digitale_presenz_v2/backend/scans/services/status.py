"""Aggregate per-scanner step outcomes into one scan status.

``Scan.status`` is a lifecycle *and* outcome field.  Before this module the
orchestrator always moved a scan from RUNNING to COMPLETED once the loop was
over, even when a required scanner had timed out or failed.  That made a
partial Nuclei run indistinguishable from a fully verified scan in the API and
in the UI.

The rules implemented here are deliberately explicit:

* COMPLETED: every required step completed, and at least one scanner produced a
  usable result.  A step skipped because a feature is disabled by deployment
  policy is optional and does not invalidate the scan.
* PARTIAL: at least one scanner produced a usable result, but at least one
  required step timed out, failed, was unavailable, was skipped (budget or
  missing registration), or is still pending.
* FAILED: no scanner produced a usable result.

Only the orchestrator calls this function after all steps have run.  A timeout
is never converted into a success just because a report file exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from scans.models import Scan
from scans.services.steps_builder import StepStatus

#: A terminal step in one of these states makes the scan incomplete.
_INCOMPLETE_STEP_STATUSES = frozenset(
    {
        StepStatus.PARTIAL,
        StepStatus.TIMEOUT,
        StepStatus.FAILED,
        StepStatus.UNAVAILABLE,
        StepStatus.PENDING,
        StepStatus.RUNNING,
    }
)

#: These statuses are conservative fallbacks for historical steps that were
#: written before ``result_usable`` existed.
_USABLE_FALLBACK_STATUSES = frozenset(
    {
        StepStatus.COMPLETED,
        StepStatus.PARTIAL,
        StepStatus.TIMEOUT,
    }
)


@dataclass(frozen=True)
class ScanStatusSummary:
    """Deterministic aggregation result for the UI, logs and ``failure_message``."""

    status: str
    reason: str
    completed: tuple[str, ...]
    incomplete: tuple[str, ...]
    usable: tuple[str, ...]


def _step_status(step: dict[str, Any]) -> str:
    return str(step.get("status") or StepStatus.PENDING)


def _step_name(step: dict[str, Any]) -> str:
    return str(step.get("scanner") or step.get("key") or "unknown")


def _is_required(step: dict[str, Any]) -> bool:
    # Steps are required unless a policy gate explicitly marked them optional.
    return bool(step.get("required", True))


def _has_usable_result(step: dict[str, Any]) -> bool:
    """Did this step produce a persisted result worth keeping?

    The orchestrator sets ``result_usable`` after ``_persist_check_result``.
    Historical scan rows do not carry that key, so a completed/partial/timeout
    step is treated as usable; failed, unavailable and skipped steps are not.
    """
    explicit = step.get("result_usable")
    if isinstance(explicit, bool):
        return explicit
    return _step_status(step) in _USABLE_FALLBACK_STATUSES


def _describe(items: Iterable[dict[str, Any]]) -> str:
    labels = [f"{_step_name(step)} {_step_status(step)}" for step in items]
    return ", ".join(labels)


def aggregate_scan_status(steps: list[dict[str, Any]] | None) -> ScanStatusSummary:
    """Return the final status for a finished orchestration pass.

    ``steps`` is ``Scan.steps`` after every scanner has run (or been skipped).
    The function never mutates the steps and never calls the database.
    """
    known = [step for step in (steps or []) if isinstance(step, dict)]
    if not known:
        return ScanStatusSummary(
            status=Scan.Status.FAILED,
            reason="Scan failed: no scanner step was defined.",
            completed=(),
            incomplete=(),
            usable=(),
        )

    completed_steps = [
        step for step in known if _step_status(step) == StepStatus.COMPLETED
    ]
    usable_steps = [step for step in known if _has_usable_result(step)]

    incomplete_steps: list[dict[str, Any]] = []
    for step in known:
        status = _step_status(step)
        # An optional step is outside the scan's coverage contract.  Whether it
        # was skipped by policy or simply unavailable (e.g. Lighthouse absent
        # from a deployment) must not downgrade an otherwise complete scan.
        if not _is_required(step):
            continue
        if status in _INCOMPLETE_STEP_STATUSES or status == StepStatus.SKIPPED:
            incomplete_steps.append(step)

    completed_names = tuple(_step_name(step) for step in completed_steps)
    incomplete_names = tuple(_step_name(step) for step in incomplete_steps)
    usable_names = tuple(_step_name(step) for step in usable_steps)

    if not usable_steps:
        detail = _describe(incomplete_steps)
        reason = "Scan failed: no usable scanner result."
        if detail:
            reason = f"{reason} Incomplete: {detail}."
        return ScanStatusSummary(
            status=Scan.Status.FAILED,
            reason=reason[:500],
            completed=completed_names,
            incomplete=incomplete_names,
            usable=(),
        )

    if not incomplete_steps:
        return ScanStatusSummary(
            status=Scan.Status.COMPLETED,
            reason="",
            completed=completed_names,
            incomplete=(),
            usable=usable_names,
        )

    detail = _describe(incomplete_steps)
    reason = (
        "Partial scan: at least one required scanner did not complete a full "
        f"run ({detail}). Results are limited to the scanners that finished; "
        "the absent checks are not proof that a finding is resolved."
    )
    return ScanStatusSummary(
        status=Scan.Status.PARTIAL,
        reason=reason[:500],
        completed=completed_names,
        incomplete=incomplete_names,
        usable=usable_names,
    )
