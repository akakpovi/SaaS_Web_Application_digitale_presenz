"""Celery tasks for the public website checker."""

from cryptography.hazmat.primitives import _cipheralgorithm
import logging
from typing import Any

from celery import chord, shared_task
from django.core.cache import cache
from django.utils import timezone

from scanners import (
    dns_scanner,
    email_security_scanner,
    performance_scanner,
    security_headers_scanner,
    ssl_scanner,
    uptime_scanner,
    website_scanner,
)
from scans.services.scoring import (
    PublicScorableResult,
    calculate_health_score,
)

logger = logging.getLogger(__name__)


PUBLIC_SCANNERS = {
    "website": website_scanner,
    "ssl": ssl_scanner,
    "dns": dns_scanner,
    "email_security": email_security_scanner,
    "security_headers": security_headers_scanner,
    "performance": performance_scanner,
    "uptime": uptime_scanner,
}


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    soft_time_limit=35,
    time_limit=40,
)
def run_public_scanner(
    self: Any,
    scanner_name: str,
    domain: str,
) -> dict[str, Any]:
    scanner = PUBLIC_SCANNERS.get(scanner_name)

    if scanner is None:
        logger.error(
            "Unknown public scanner",
            extra={"scanner": scanner_name},
        )

        return {
            "category": scanner_name,
            "score": 0,
            "status": "critical",
            "message": "Scanner unavailable.",
            "details": {},
        }

    try:
        logger.info(
            "Running public scanner",
            extra={
                "scanner": scanner_name,
                "domain": domain,
            },
        )

        result = scanner.scan(domain)

        return {
            "category": scanner_name,
            "score": result.score,
            "status": result.status,
            "message": result.message,
            "details": result.details,
        }

    except Exception as exc:
        logger.exception(
            "Public scanner failed",
            extra={
                "scanner": scanner_name,
                "domain": domain,
            },
        )

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        return {
            "category": scanner_name,
            "score": 0,
            "status": "critical",
            "message": "The check could not be completed.",
            "details": {},
        }


@shared_task
def finalize_public_scan(
    results: list[dict[str, Any]],
    domain: str,
    scan_id: str,
) -> dict[str, Any]:
    try:
        scorable_results = [
            PublicScorableResult(
                category=result["category"],
                score=result.get("score"),
                status=result["status"],
            )
            for result in results
        ]

        health = calculate_health_score(scorable_results)

        final_result: dict[str, Any] = {
            "id": scan_id,
            "scan_id": scan_id,
            "domain": domain,
            "status": "completed",
            "progress": 100,
            "health_score": health.score,
            "health_status": str(health.status),
            "scanned_at": timezone.now().isoformat(),
            "checks": results,
        }
        cache.set(
            f"public_scan:{scan_id}",
            final_result,
            timeout=900,
        )

        # Also cache by normalized domain.
        cache.set(
            f"public_scan_domain:{domain}",
            final_result,
            timeout=900,
        )

        logger.info(
            "Public scan completed",
            extra={
                "domain": domain,
                "scan_id": scan_id,
                "health_score": health.score,
            },
        )

        return final_result

    except Exception:
        logger.exception(
            "Failed to finalize public scan",
            extra={
                "domain": domain,
                "scan_id": scan_id,
            },
        )

        error_result = {
    "id": scan_id,
    "scan_id": scan_id,
    "domain": domain,
    "status": "failed",
    "progress": 100,
    "health_score": None,
    "health_status": None,
    "checks": [],
    "message": "The scan could not be completed.",
    "scanned_at": timezone.now().isoformat(),
}

        cache.set(
            f"public_scan:{scan_id}",
            error_result,
            timeout=900,
        )

        return error_result


@shared_task
def run_public_scan(
    domain: str,
    scan_id: str,
) -> str:
    scanner_tasks = [
        run_public_scanner.s(scanner_name, domain)
        for scanner_name in PUBLIC_SCANNERS
    ]

    chord(scanner_tasks)(
        finalize_public_scan.s(domain, scan_id)
    )

    return scan_id