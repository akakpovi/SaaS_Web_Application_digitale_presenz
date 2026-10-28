"""Celery tasks for the Scan Engine.

Primary task: ``run_authenticated_scan`` — the real orchestrator entry point.

All other scan-related background work lives here too (purge, cancel, etc.).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


#: Scan types that must end up with a numeric health_score.
_SCORED_SCAN_TYPES = ("health", "full")


def _dispatch_alert_detection(scan_id: int) -> bool:
    """Queue ``alerts.tasks.detect_alerts`` for a freshly completed scan.

    The alert engine was fully implemented but never triggered: nothing in the
    scan pipeline called ``detect_alerts``, so the ``Alert`` table stayed empty
    no matter how many scans ran.  This is the single wiring point that closes
    the loop.

    Alert detection is a *side effect* of a successful scan: a broken alert
    pipeline (broker down, …) must never turn a completed scan into a failed
    one.  Failures are therefore logged, not raised.
    """
    try:
        from alerts.tasks import detect_alerts

        detect_alerts.delay(scan_id)
        logger.info("Alert detection queued for scan %d", scan_id)
        return True
    except Exception:
        logger.exception(
            "Could not queue alert detection for scan %d — scan result is "
            "still valid, alerts will be missing until the next scan",
            scan_id,
        )
        return False


def _dispatch_scan_issue_alert(scan_id: int) -> bool:
    """Queue the coverage/failure alert for a non-completed scan.

    The alert explains that the run did not cover every required check; it
    never resolves existing findings.  Like the other side effects, a broker
    outage must not change the scan outcome.
    """
    try:
        from alerts.tasks import report_scan_issue

        report_scan_issue.delay(scan_id)
        logger.info("Coverage alert queued for scan %d", scan_id)
        return True
    except Exception:
        logger.exception(
            "Could not queue the coverage alert for scan %d — the scan status "
            "is still accurate, the owner will not be notified",
            scan_id,
        )
        return False


def _record_monitoring_outcome(scan) -> None:
    """Feed the scan outcome back into the monitoring schedule.

    ``MonitoringConfig.record_failure``/``record_success`` existed but nothing
    ever called them, so ``consecutive_failures`` stayed at zero and the
    dashboard reported a healthy schedule even while every run failed.  The
    counter now tracks real terminal outcomes.
    """
    from monitoring.models import MonitoringConfig
    from scans.models import Scan

    config = MonitoringConfig.objects.filter(website_id=scan.website_id).first()
    if config is None:
        return
    if scan.status == Scan.Status.COMPLETED:
        config.record_success()
    elif scan.status in (Scan.Status.FAILED, Scan.Status.PARTIAL):
        config.record_failure()


def _dispatch_advisor(scan_id: int) -> bool:
    """Queue the AI advisor for a completed scan, never failing the scan.

    The advisor is a side effect of a successful scan.  A disabled flag, a
    broker outage or an import error must therefore be logged and swallowed.
    The task itself repeats the feature-flag and scan-status checks so a
    stale queued message cannot bypass a kill switch.
    """
    if not getattr(settings, "AI_ADVISOR_ENABLED", False):
        logger.info("AI advisor disabled for scan %d", scan_id)
        return False
    try:
        from advisory.tasks import generate_scan_recommendations_task

        generate_scan_recommendations_task.delay(scan_id)
        logger.info("AI advisor queued for scan %d", scan_id)
        return True
    except Exception:
        logger.exception(
            "Could not queue AI advisor for scan %d — scan result is still "
            "valid, recommendations will be missing",
            scan_id,
        )
        return False


def _finalize_scan(scan_id: int) -> dict:
    """Verify and repair the terminal state of a completed scan.

    A scan is only useful to the product when it ends up COMPLETED or PARTIAL
    with the artefacts it actually produced.  Historically the pipeline
    aborted before writing any of that (``Severity.UNKNOWN`` AttributeError),
    leaving 2 600+ completed scans with ``health_score = NULL`` and zero
    findings.

    This function makes that failure mode impossible to reach silently: it
    recomputes the score and logs an explicit diagnostic when the scan is
    empty.  A PARTIAL scan keeps the score computed from the checks that did
    run, but it is never forced to 0 and never presented as a complete scan.
    """
    from scans.models import CheckResult, Finding, Scan, ScannerRun
    from scans.services.scoring import recalculate_scan_health

    report: dict = {"scan_id": scan_id, "status": None, "repaired": False}

    try:
        scan = Scan.objects.get(pk=scan_id)
    except Scan.DoesNotExist:
        logger.error("Scan %d vanished before finalization", scan_id)
        return report

    report["status"] = scan.status

    _record_monitoring_outcome(scan)

    if scan.status not in (Scan.Status.COMPLETED, Scan.Status.PARTIAL):
        logger.warning(
            "Scan %d ended in status=%s (failure_message=%r) — not finalizing",
            scan_id,
            scan.status,
            scan.failure_message,
        )
        return report

    checks = CheckResult.objects.filter(scan=scan)
    findings = Finding.objects.filter(scanner_run__scan=scan)
    report["check_results"] = checks.count()
    report["findings"] = findings.count()
    report["scanner_runs"] = ScannerRun.objects.filter(scan=scan).count()
    report["failed_scanner_runs"] = ScannerRun.objects.filter(
        scan=scan,
        status__in=(
            ScannerRun.Status.FAILED,
            ScannerRun.Status.TIMEOUT,
            ScannerRun.Status.PARTIAL,
            ScannerRun.Status.UNAVAILABLE,
        ),
    ).count()

    health = recalculate_scan_health(scan)

    if (
        scan.status == Scan.Status.COMPLETED
        and health.score is None
        and scan.scan_type in _SCORED_SCAN_TYPES
    ):
        logger.error(
            "Scan %d completed with score=None (type=%s, check_results=%d) — "
            "forcing score=0 so the API never exposes a NULL score",
            scan_id,
            scan.scan_type,
            report["check_results"],
        )
        Scan.objects.filter(pk=scan_id).update(health_score=0)
        report["score_forced"] = True

    if report["check_results"] == 0:
        logger.error(
            "Scan %d ended %s without a single CheckResult — every scanner "
            "failed, timed out or was unavailable (failed_runs=%d)",
            scan_id,
            scan.status,
            report["failed_scanner_runs"],
        )
    elif report["findings"] == 0:
        logger.warning(
            "Scan %d ended %s with %d CheckResult(s) but no Finding — the "
            "finding normalisation is not producing records",
            scan_id,
            scan.status,
            report["check_results"],
        )

    report["health_score"] = Scan.objects.filter(pk=scan_id).values_list(
        "health_score", flat=True
    ).first()
    report["repaired"] = bool(report.get("score_forced"))

    logger.info(
        "Scan %d finalized: score=%s check_results=%d findings=%d",
        scan_id,
        report["health_score"],
        report["check_results"],
        report["findings"],
    )
    return report


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="scans.tasks.run_authenticated_scan",
    # Per-task time limits — override the global 600s for health scans (should be faster)
    time_limit=600,
    soft_time_limit=570,
)
def run_authenticated_scan(self, scan_id: int) -> dict:
    """Execute a full scan via the ScanOrchestrator.

    This is the real implementation.  The previous stub that just set
    status=COMPLETED without running any scanners has been replaced.

    The task is idempotent: if the scan is already COMPLETED, PARTIAL, FAILED
    or CANCELLED, the orchestrator exits immediately.
    """
    from scans.services.orchestrator import ScanOrchestrator
    from scans.models import Scan

    logger.info("Starting scan task for scan_id=%d", scan_id)
    try:
        orchestrator = ScanOrchestrator(scan_id=scan_id)
        orchestrator.run()
        # Guarantee the terminal state is usable (score + artefacts written).
        report = _finalize_scan(scan_id)
        # Alerts and AI analysis are only launched for a fully verified scan.
        # A PARTIAL scan keeps its stored findings for diagnosis, but it must
        # not trigger an automatic resolution or be analysed as complete.
        if report.get("status") == Scan.Status.COMPLETED:
            report["alerts_queued"] = _dispatch_alert_detection(scan_id)
            report["advisor_queued"] = _dispatch_advisor(scan_id)
        elif report.get("status") in (Scan.Status.FAILED, Scan.Status.PARTIAL):
            # Incomplete coverage is an incident: report it, never resolve on
            # it.  ``report_scan_issue`` only creates/widens that alert.
            report["coverage_alert_queued"] = _dispatch_scan_issue_alert(scan_id)
        logger.info("Scan task completed for scan_id=%d", scan_id)
        return {"scan_id": scan_id, "status": "done", **report}
    except Exception as exc:
        logger.exception("Scan task failed for scan_id=%d: %s", scan_id, exc)
        # Mark scan as failed if the orchestrator itself crashed.
        try:
            scan = Scan.objects.get(pk=scan_id)
            if scan.status not in (
                Scan.Status.COMPLETED,
                Scan.Status.PARTIAL,
                Scan.Status.FAILED,
                Scan.Status.CANCELLED,
            ):
                scan.transition_to(Scan.Status.FAILED, failure_message=str(exc)[:500])
                _record_monitoring_outcome(scan)
                _dispatch_scan_issue_alert(scan_id)
        except Exception:
            pass
        raise


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="scans.tasks.run_health_scan",
    time_limit=300,
    soft_time_limit=280,
)
def run_health_scan(self, scan_id: int) -> dict:
    """Convenience alias: run a HEALTH-type scan."""
    return run_authenticated_scan.apply(args=[scan_id]).get()


@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=60,
    name="scans.tasks.run_security_scan",
    time_limit=600,
    soft_time_limit=570,
)
def run_security_scan(self, scan_id: int) -> dict:
    """Convenience alias: run a SECURITY-type scan (external tools)."""
    return run_authenticated_scan.apply(args=[scan_id]).get()


def _reap_after_seconds(name: str, default: int) -> int:
    """Read a positive reaper threshold from settings, with a safe floor.

    The floor is five minutes: a scan is never reaped before Celery's own
    ``time_limit`` (600 s) has had a chance to kill it.
    """
    raw = getattr(settings, name, default)
    try:
        return max(300, int(raw))
    except (TypeError, ValueError):
        return default


@shared_task(name="scans.tasks.reap_stale_scans")
def reap_stale_scans() -> dict:
    """Fail scans abandoned by a crashed worker or a lost queue message.

    ``TriggerImmediateScanView`` refuses a new scan while another one is
    pending/queued/running (HTTP 409).  A scan whose worker died would
    therefore block its website forever.  The sweep re-checks each candidate
    under a row lock so it can never overwrite a scan that just progressed.
    """
    from scans.models import Scan

    now = timezone.now()
    running_cutoff = now - timedelta(
        seconds=_reap_after_seconds("SCAN_REAP_RUNNING_AFTER_SECONDS", 900)
    )
    queued_cutoff = now - timedelta(
        seconds=_reap_after_seconds("SCAN_REAP_QUEUED_AFTER_SECONDS", 900)
    )
    candidates = list(
        Scan.objects.filter(
            Q(status=Scan.Status.RUNNING, updated_at__lt=running_cutoff)
            | Q(
                status__in=[Scan.Status.QUEUED, Scan.Status.PENDING],
                updated_at__lt=queued_cutoff,
            )
        )
        .order_by("updated_at")
        .values_list("id", flat=True)[:200]
    )

    reaped: list[int] = []
    for scan_id in candidates:
        previous_status = ""
        idle_seconds = 0
        with transaction.atomic():
            scan = Scan.objects.select_for_update().get(pk=scan_id)
            cutoff = (
                running_cutoff
                if scan.status == Scan.Status.RUNNING
                else queued_cutoff
            )
            if (
                scan.status
                not in {Scan.Status.PENDING, Scan.Status.QUEUED, Scan.Status.RUNNING}
                or scan.updated_at >= cutoff
            ):
                continue
            previous_status = scan.status
            idle_seconds = max(0, int((now - scan.updated_at).total_seconds()))
            scan.transition_to(
                Scan.Status.FAILED,
                failure_message=(
                    "Scan abandoned: no progress since "
                    f"{scan.updated_at.isoformat()}; reaped automatically"
                ),
            )
            reaped.append(scan_id)

        logger.error(
            "scan_reaped scan_id=%d previous_status=%s idle_s=%d "
            "error_code=stale_scan_reaped",
            scan_id,
            previous_status,
            idle_seconds,
        )
        _record_monitoring_outcome(scan)
        _dispatch_scan_issue_alert(scan_id)

    logger.info(
        "scan_reaper running_cutoff=%s queued_cutoff=%s reaped=%d",
        running_cutoff.isoformat(),
        queued_cutoff.isoformat(),
        len(reaped),
    )
    from core.reaper_metrics import record_reaper_tick

    record_reaper_tick(kind="scans", reaped=len(reaped))
    return {
        "running_cutoff": running_cutoff.isoformat(),
        "queued_cutoff": queued_cutoff.isoformat(),
        "reaped": len(reaped),
        "scan_ids": reaped[:50],
    }


@shared_task(name="scans.tasks.cancel_scan")
def cancel_scan(scan_id: int) -> dict:
    """Attempt to cancel a running or queued scan."""
    from scans.models import Scan

    try:
        scan = Scan.objects.get(pk=scan_id)
        if scan.is_active:
            scan.transition_to(Scan.Status.CANCELLED)
            logger.info("Scan %d cancelled", scan_id)
            return {"scan_id": scan_id, "cancelled": True}
        return {"scan_id": scan_id, "cancelled": False, "reason": scan.status}
    except Scan.DoesNotExist:
        return {"scan_id": scan_id, "cancelled": False, "reason": "not_found"}


@shared_task(name="scans.tasks.prune_scanner_archives")
def prune_scanner_archives() -> dict:
    """Enforce the configured retention for private raw scanner reports."""
    from scanners.artifacts import prune_scan_archives

    try:
        result = prune_scan_archives()
        logger.info("Scanner archive retention applied: %s", result)
        return result
    except Exception:
        # Retention is maintenance: a broken archive volume must never stop
        # scans or other periodic jobs.
        logger.exception("Scanner archive retention failed")
        return {"enabled": True, "deleted": 0, "kept": 0, "errors": 1}


@shared_task(name="scans.tasks.purge_guest_data")
def purge_guest_data() -> dict:
    """Nightly purge of guest scan data older than 24 hours."""
    from scans.models import Scan
    from websites.models import Website

    cutoff = timezone.now() - timedelta(hours=24)
    scans_deleted, _ = Scan.objects.filter(is_guest=True, created_at__lt=cutoff).delete()
    websites_deleted, _ = Website.objects.filter(is_guest=True, created_at__lt=cutoff).delete()
    logger.info(
        "Nightly purge: %d scans and %d guest websites deleted",
        scans_deleted,
        websites_deleted,
    )
    return {"scans_deleted": scans_deleted, "websites_deleted": websites_deleted}
