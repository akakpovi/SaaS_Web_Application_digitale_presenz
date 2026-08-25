from dataclasses import dataclass
from typing import Iterable, Protocol

from scans.models import CheckResult, HealthStatus, Scan


CHECK_WEIGHTS: dict[str, int] = {
    CheckResult.Category.WEBSITE: 20,
    CheckResult.Category.SSL: 20,
    CheckResult.Category.DNS: 15,
    CheckResult.Category.EMAIL_SECURITY: 15,
    CheckResult.Category.SECURITY_HEADERS: 15,
    CheckResult.Category.PERFORMANCE: 15,
}


class ScorableResult(Protocol):
    category: str
    score: int | None
    status: str


@dataclass(frozen=True)
class HealthScore:
    score: int | None
    status: str


@dataclass(frozen=True)
class PublicScorableResult:
    category: str
    score: int | None
    status: str


def calculate_health_score(
    results: Iterable[ScorableResult],
) -> HealthScore:
    """
    Calculate the deterministic global health score.

    Scanner scores are already capped to their category weight:
    website=20, ssl=20, dns=15, email_security=15,
    security_headers=15, performance=15.

    Uptime is deliberately excluded from the global score.

    Missing weighted checks contribute zero once at least one
    weighted result exists.
    """
    weighted_results = {
        result.category: result
        for result in results
        if result.category in CHECK_WEIGHTS
    }

    if not weighted_results:
        return HealthScore(
            score=None,
            status=HealthStatus.NEUTRAL,
        )

    score = sum(
        result.score or 0
        for result in weighted_results.values()
    )

    # Defensive bound.
    score = max(0, min(100, score))

    if (
        any(
            result.status == HealthStatus.CRITICAL
            for result in weighted_results.values()
        )
        or score < 40
    ):
        health_status = HealthStatus.CRITICAL

    elif (
        any(
            result.status == HealthStatus.WARNING
            for result in weighted_results.values()
        )
        or score < 80
    ):
        health_status = HealthStatus.WARNING

    else:
        health_status = HealthStatus.HEALTHY

    return HealthScore(
        score=score,
        status=health_status,
    )


def recalculate_scan_health(scan: Scan) -> HealthScore:
    health = calculate_health_score(
        scan.check_results.all()
    )

    Scan.objects.filter(pk=scan.pk).update(
        health_score=health.score,
        health_status=health.status,
    )

    scan.health_score = health.score
    scan.health_status = health.status

    return health