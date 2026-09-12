import logging
from datetime import date, timedelta
from typing import Any

from django.db.models import Avg, Count, Max, Min
from django.utils import timezone

from scans.models import CheckResult, Scan
from websites.models import Website

logger = logging.getLogger(__name__)


def generate_report_data(website: Website, period_start: date, period_end: date) -> dict[str, Any]:
    """
    Build report data from historical scans between period_start and period_end.
    Returns a dict matching Report model fields.
    """
    scans = Scan.objects.filter(
        website=website,
        status=Scan.Status.COMPLETED,
        created_at__date__gte=period_start,
        created_at__date__lte=period_end,
    ).order_by("created_at")

    total_scans = scans.count()
    if total_scans == 0:
        return {
            "current_score": None,
            "previous_score": None,
            "score_change": None,
            "check_breakdown": {},
            "improvements": [],
            "problems": [],
            "recommendations": [],
            "score_history": [],
            "total_scans": 0,
        }

    # Score history
    score_history = [
        {
            "date": s.created_at.date().isoformat(),
            "score": s.health_score,
            "status": s.health_status,
        }
        for s in scans
        if s.health_score is not None
    ]

    # Current and previous scores
    current_scan  = scans.last()
    previous_scan = scans.first()
    current_score  = current_scan.health_score  if current_scan  else None
    previous_score = previous_scan.health_score if previous_scan else None
    score_change   = (current_score - previous_score) if (current_score is not None and previous_score is not None) else None

    # Check breakdown — average score per category across all scans
    check_breakdown: dict[str, Any] = {}
    for category in CheckResult.Category.values:
        results = CheckResult.objects.filter(
            scan__in=scans, category=category
        ).exclude(score__isnull=True)
        if results.exists():
            avg_score = results.aggregate(avg=Avg("score"))["avg"]
            statuses  = list(results.values_list("status", flat=True))
            check_breakdown[category] = {
                "avg_score": round(avg_score, 1) if avg_score else None,
                "critical_count": statuses.count("critical"),
                "warning_count":  statuses.count("warning"),
                "healthy_count":  statuses.count("healthy"),
            }

    # Improvements and problems from latest scan
    improvements: list[str] = []
    problems: list[str] = []
    recommendations: list[str] = []

    if current_scan:
        latest_results = CheckResult.objects.filter(scan=current_scan)
        for result in latest_results:
            if result.status == "healthy":
                improvements.append(f"{result.category}: {result.summary}")
            elif result.status in ("critical", "warning"):
                problems.append(f"{result.category}: {result.summary}")
            if result.recommendation:
                recommendations.append(result.recommendation)

    return {
        "current_score":   current_score,
        "previous_score":  previous_score,
        "score_change":    score_change,
        "check_breakdown": check_breakdown,
        "improvements":    improvements[:10],
        "problems":        problems[:10],
        "recommendations": recommendations[:10],
        "score_history":   score_history,
        "total_scans":     total_scans,
    }
