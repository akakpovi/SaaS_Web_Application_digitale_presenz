"""Celery entry point for AI recommendation generation.

The scan pipeline only enqueues this task.  Every failure path is contained
here: a provider outage, a malformed model answer or a broker problem must
never turn an otherwise successful website scan into a failed scan.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

_DEFAULT_RETRY_COUNTDOWN = 120

#: Terminal labels returned by the Celery task.  ``failed_quota_exhausted``
#: used to be returned for every exhausted retry, including a persistent 500;
#: the label now reflects the actual cause.
_QUOTA_ERROR_CODES = frozenset({"rate_limit_exceeded", "guest_quota_exceeded"})
_CONFIGURATION_ERROR_CODES = frozenset({"invalid_api_key", "client_unavailable"})


def _terminal_status(error_code: str) -> str:
    if error_code in _QUOTA_ERROR_CODES:
        return "failed_quota_exhausted"
    if error_code in _CONFIGURATION_ERROR_CODES:
        return "failed_configuration"
    return "failed_upstream_error"


@shared_task(
    bind=True,
    name="advisory.tasks.generate_scan_recommendations_task",
    max_retries=3,
    default_retry_delay=_DEFAULT_RETRY_COUNTDOWN,
    # The client may try two models with its own bounded HTTP retries.  Keep
    # enough headroom for the whole failover chain before Celery kills it.
    time_limit=600,
    soft_time_limit=570,
)
def generate_scan_recommendations_task(self, scan_id: int) -> dict:
    """Generate recommendations for a completed authenticated scan.

    The feature flag is checked both by the dispatcher and here, so an old
    queued message cannot generate billable AI traffic after a kill switch.
    """
    if not getattr(settings, "AI_ADVISOR_ENABLED", False):
        logger.info("AI advisor disabled; skipping scan %s", scan_id)
        return {"scan_id": scan_id, "status": "disabled"}

    from scans.models import Scan

    scan = Scan.objects.filter(pk=scan_id).only(
        "id", "status", "is_guest"
    ).first()
    if scan is None:
        return {"scan_id": scan_id, "status": "not_found"}
    if scan.is_guest:
        return {"scan_id": scan_id, "status": "skipped_guest"}
    if scan.status != Scan.Status.COMPLETED:
        return {
            "scan_id": scan_id,
            "status": "skipped_not_completed",
            "scan_status": scan.status,
        }

    from advisory.services.advisor import generate_recommendations_for_scan

    retries = int(getattr(self.request, "retries", 0) or 0)
    try:
        result = generate_recommendations_for_scan(
            scan_id,
            retry_failed=retries > 0,
        )
    except Exception as exc:
        # The run record is the source of truth for the failure.  Do not leak
        # provider bodies or prompt data into the Celery result or logs.
        logger.exception(
            "AI advisor task failed scan=%s error=%s",
            scan_id,
            exc.__class__.__name__,
        )
        return {
            "scan_id": scan_id,
            "status": "error",
            "error": exc.__class__.__name__,
        }

    payload = {
        "scan_id": scan_id,
        "status": result.run.status,
        "run_id": str(result.run.id),
        "used_fallback": result.used_fallback,
        "model_used": result.run.model_used,
        "recommendations": len(result.recommendations),
        "error_code": result.error_code,
    }

    if result.should_retry:
        max_countdown = int(
            getattr(settings, "AI_ADVISOR_RETRY_MAX_SECONDS", 900)
        )
        countdown = min(
            max(result.retry_after_seconds or _DEFAULT_RETRY_COUNTDOWN, 30),
            max_countdown,
        )
        if retries < self.max_retries:
            logger.warning(
                "AI advisor retry scheduled scan=%s code=%s in %ss "
                "(attempt %s/%s)",
                scan_id,
                result.error_code or "unknown",
                countdown,
                retries + 1,
                self.max_retries,
            )
            raise self.retry(countdown=countdown)
        payload["status"] = _terminal_status(result.error_code)

    logger.info(
        "AI advisor finished scan=%s status=%s fallback=%s model=%s",
        scan_id,
        payload["status"],
        result.used_fallback,
        result.run.model_used or "-",
    )
    return payload


@shared_task(name="advisory.tasks.reap_stale_ai_runs")
def reap_stale_ai_runs() -> dict:
    """Fail AI runs abandoned by a crashed or killed worker.

    A run is claimed as ``running`` before the provider call.  If the worker
    dies (OOM, ``time_limit`` kill, container restart), nothing ever updates
    the row and the scan keeps showing an analysis in progress forever.  This
    periodic sweep makes the failure explicit and visible.
    """
    from advisory.models import AIRecommendationRun
    from advisory.services.advisor import stale_run_cutoff

    cutoff = stale_run_cutoff()
    now = timezone.now()
    candidates = AIRecommendationRun.objects.filter(
        status__in=[
            AIRecommendationRun.Status.RUNNING,
            AIRecommendationRun.Status.PENDING,
        ],
        updated_at__lt=cutoff,
    ).values_list("id", "scan_id", "attempts", "updated_at")

    reaped: list[str] = []
    for run_id, scan_id, attempts, updated_at in candidates.iterator():
        claimed = AIRecommendationRun.objects.filter(
            pk=run_id,
            status__in=[
                AIRecommendationRun.Status.RUNNING,
                AIRecommendationRun.Status.PENDING,
            ],
            updated_at__lt=cutoff,
        ).update(
            status=AIRecommendationRun.Status.FAILED,
            error_code="stale_run_reaped",
            completed_at=now,
            updated_at=now,
        )
        if not claimed:
            # A worker finished or reclaimed the run between the query and
            # the update; leave it alone.
            continue
        age_seconds = max(0, int((now - updated_at).total_seconds()))
        logger.error(
            "ai_advisor_run_reaped run_id=%s scan_id=%s attempts=%s "
            "idle_s=%d error_code=stale_run_reaped",
            run_id,
            scan_id,
            attempts,
            age_seconds,
        )
        reaped.append(str(run_id))

    logger.info(
        "ai_advisor_reaper cutoff=%s reaped=%d",
        cutoff.isoformat(),
        len(reaped),
    )
    return {
        "cutoff": cutoff.isoformat(),
        "reaped": len(reaped),
        "run_ids": reaped[:50],
    }


@shared_task(
    name="advisory.tasks.verify_aka_credentials",
    time_limit=60,
    soft_time_limit=50,
)
def verify_aka_credentials() -> dict:
    """Probe the gateway with the configured key and alert on guest mode.

    This is the standing early-warning signal: without it an invalid key is
    only discovered when a customer scan produces no recommendations.
    """
    from advisory.services.aka_client import AkaAuthenticationError, AkaError
    from advisory.services.factory import (
        build_aka_client,
        clear_aka_credentials_invalid,
        mark_aka_credentials_invalid,
    )

    try:
        client = build_aka_client()
    except Exception as exc:
        mark_aka_credentials_invalid(exc.__class__.__name__)
        logger.error(
            "aka_ai_credentials_invalid source=probe reason=%s",
            exc.__class__.__name__,
        )
        return {"status": "invalid", "reason": exc.__class__.__name__}

    messages = [{"role": "user", "content": "Reply with the single word: pong"}]
    try:
        with client:
            completion = client.chat(messages, max_tokens=1, temperature=0)
    except AkaAuthenticationError:
        mark_aka_credentials_invalid("invalid_api_key")
        logger.error("aka_ai_credentials_invalid source=probe status=guest_mode")
        return {"status": "invalid", "reason": "invalid_api_key"}
    except AkaError as exc:
        # Unreachable provider is not an invalid key: do not poison the cache.
        logger.warning(
            "aka_ai_credentials_probe_unreachable error=%s",
            exc.__class__.__name__,
        )
        return {"status": "unreachable", "reason": exc.__class__.__name__}

    clear_aka_credentials_invalid()
    logger.info("aka_ai_credentials_ok model=%s", completion.model or "-")
    return {"status": "ok", "model": completion.model}
