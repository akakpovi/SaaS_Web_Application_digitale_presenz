"""Recommendation Engine.

Produces prioritised, human-readable recommendations from a scan's findings
and check results.  Extends the existing scoring system rather than replacing
it.

Usage::

    from scans.services.recommendation_engine import RecommendationEngine

    engine = RecommendationEngine(scan)
    recommendations = engine.generate()
    # recommendations → list of Recommendation ordered by priority
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# Priority levels (lower number = higher priority).
class Priority:
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    INFO = 5


@dataclass(order=True)
class Recommendation:
    """A single, actionable recommendation."""

    priority: int
    """Lower is more urgent. Use Priority constants."""

    sort_index: int = field(init=False, repr=False)

    category: str = field(compare=False)
    title: str = field(compare=False)
    description: str = field(compare=False, default="")
    action: str = field(compare=False, default="")
    impact: str = field(compare=False, default="")
    effort: str = field(compare=False, default="medium")  # low/medium/high
    reference_url: str = field(compare=False, default="")
    check_code: str = field(compare=False, default="")

    def __post_init__(self) -> None:
        self.sort_index = self.priority


def _map_severity_to_priority(severity: str) -> int:
    return {
        "critical": Priority.CRITICAL,
        "high": Priority.HIGH,
        "medium": Priority.MEDIUM,
        "low": Priority.LOW,
        "info": Priority.INFO,
    }.get(severity.lower(), Priority.MEDIUM)


def _map_status_to_priority(status: str) -> int:
    return {
        "critical": Priority.CRITICAL,
        "warning": Priority.MEDIUM,
        "healthy": Priority.INFO,
        "neutral": Priority.INFO,
    }.get(status.lower(), Priority.MEDIUM)


class RecommendationEngine:
    """Generates prioritised recommendations from a scan's results.

    Sources:
    1. ``Finding`` records (from external scanner runs) — granular
    2. ``CheckResult`` records (from internal health checks) — aggregated
    """

    def __init__(self, scan: Any) -> None:
        self.scan = scan

    def generate(self) -> list[Recommendation]:
        """Return recommendations ordered by priority (most urgent first)."""
        recommendations: list[Recommendation] = []

        # 1. From Findings (granular, new pipeline).
        recommendations.extend(self._from_findings())

        # 2. From CheckResults (aggregated, legacy health pipeline).
        recommendations.extend(self._from_check_results())

        # Deduplicate by check_code, keep highest priority (lowest number).
        seen: dict[str, Recommendation] = {}
        for rec in recommendations:
            if rec.check_code and rec.check_code in seen:
                if rec.priority < seen[rec.check_code].priority:
                    seen[rec.check_code] = rec
            else:
                key = rec.check_code or f"{rec.category}:{rec.title}"
                seen[key] = rec

        return sorted(seen.values())

    def _from_findings(self) -> list[Recommendation]:
        """Generate recommendations from Finding records."""
        from scans.models import Finding

        recommendations: list[Recommendation] = []
        findings = Finding.objects.filter(
            scanner_run__scan=self.scan,
            status__in=["fail", "warning"],
        ).exclude(recommendation="").select_related("scanner_run")

        for finding in findings:
            if not finding.recommendation:
                continue
            priority = _map_severity_to_priority(finding.severity)
            effort = "low" if finding.severity == "info" else (
                "high" if finding.severity in ("high", "critical") else "medium"
            )
            recommendations.append(Recommendation(
                priority=priority,
                category=finding.category,
                title=finding.title,
                description=finding.description,
                action=finding.recommendation,
                impact=self._severity_to_impact(finding.severity),
                effort=effort,
                reference_url=finding.reference_url,
                check_code=finding.check_code,
            ))

        return recommendations

    def _from_check_results(self) -> list[Recommendation]:
        """Generate recommendations from CheckResult records."""
        recommendations: list[Recommendation] = []
        check_results = self.scan.check_results.exclude(
            recommendation=""
        ).exclude(status="healthy")

        for result in check_results:
            priority = _map_status_to_priority(result.status)
            recommendations.append(Recommendation(
                priority=priority,
                category=result.category,
                title=f"Improve {result.category.replace('_', ' ').title()}",
                description=result.summary,
                action=result.recommendation,
                impact=self._status_to_impact(result.status),
                effort="medium",
                check_code=f"{result.category}.overall",
            ))

        return recommendations

    def to_dict_list(self) -> list[dict[str, Any]]:
        """Return recommendations as a list of dicts (API-serializable)."""
        return [
            {
                "priority": rec.priority,
                "category": rec.category,
                "title": rec.title,
                "description": rec.description,
                "action": rec.action,
                "impact": rec.impact,
                "effort": rec.effort,
                "reference_url": rec.reference_url,
                "check_code": rec.check_code,
            }
            for rec in self.generate()
        ]

    @staticmethod
    def _severity_to_impact(severity: str) -> str:
        return {
            "critical": "Immediate risk of breach or data exposure",
            "high": "High security risk requiring urgent attention",
            "medium": "Moderate risk — remediate in next release cycle",
            "low": "Low risk — schedule for future hardening",
            "info": "Informational — no immediate action required",
        }.get(severity.lower(), "Unknown impact")

    @staticmethod
    def _status_to_impact(status: str) -> str:
        return {
            "critical": "Critical issue affecting security or availability",
            "warning": "Warning — potential risk if not addressed",
            "healthy": "No action required",
            "neutral": "Unable to assess — verify configuration",
        }.get(status.lower(), "Unknown impact")
