"""Real monitoring aggregates — no synthetic series.

The authenticated Monitoring page needs more than the raw config list: an
uptime history, a per-website status and an event timeline.  Everything here
is derived from records the platform already wrote (``Scan``, ``CheckResult``
and ``Alert``); nothing is generated, extrapolated or randomised.  When a user
has no measurement yet the payload is explicitly empty so the UI can render an
honest "no check recorded yet" state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.utils import timezone

from alerts.models import Alert
from monitoring.models import MonitoringConfig
from scans.models import CheckResult, Scan
from websites.models import Website

#: period key -> (look-back duration, bucket width)
PERIODS: dict[str, tuple[timedelta, timedelta]] = {
    "24H": (timedelta(hours=24), timedelta(hours=1)),
    "7D": (timedelta(days=7), timedelta(days=1)),
    "30D": (timedelta(days=30), timedelta(days=1)),
    "90D": (timedelta(days=90), timedelta(days=7)),
}

DEFAULT_PERIOD = "24H"


@dataclass(frozen=True)
class Period:
    key: str
    start: datetime
    end: datetime
    bucket: timedelta

    @property
    def bucket_count(self) -> int:
        return max(1, int((self.end - self.start) / self.bucket))


def resolve_period(key: str | None, now: datetime | None = None) -> Period:
    key = (key or DEFAULT_PERIOD).upper()
    if key not in PERIODS:
        key = DEFAULT_PERIOD
    duration, bucket = PERIODS[key]
    end = now or timezone.now()
    return Period(key=key, start=end - duration, end=end, bucket=bucket)


def _is_up(details: dict | None, status: str) -> bool:
    """A sample counts as available when the uptime probe said so.

    ``UptimeScanner`` stores ``current_status`` in ``technical_details``.  The
    status column is a fallback for older rows written before that key existed.
    """
    if isinstance(details, dict) and details.get("current_status") in {"up", "down"}:
        return details["current_status"] == "up"
    return status == "healthy"


def _uptime_rows(user, period: Period, website_id: int | None):
    qs = CheckResult.objects.filter(
        scan__website__owner=user,
        scan__status=Scan.Status.COMPLETED,
        category=CheckResult.Category.UPTIME,
        scan__created_at__gte=period.start,
        scan__created_at__lte=period.end,
    )
    if website_id is not None:
        qs = qs.filter(scan__website_id=website_id)
    return qs.values_list("scan__created_at", "technical_details", "status")


def _series(user, period: Period, website_id: int | None) -> list[dict]:
    buckets = [
        {"up": 0, "total": 0}
        for _ in range(period.bucket_count)
    ]

    for created_at, details, status in _uptime_rows(user, period, website_id):
        index = int((created_at - period.start) / period.bucket)
        if index < 0 or index >= len(buckets):
            continue
        buckets[index]["total"] += 1
        if _is_up(details, status):
            buckets[index]["up"] += 1

    series: list[dict] = []
    for index, bucket in enumerate(buckets):
        if not bucket["total"]:
            continue
        series.append(
            {
                "bucket_start": (
                    period.start + index * period.bucket
                ).isoformat(),
                "uptime_percent": round(bucket["up"] / bucket["total"] * 100, 2),
                "checks": bucket["total"],
                "downtime_checks": bucket["total"] - bucket["up"],
            }
        )
    return series


def _summary(user, period: Period, website_id: int | None) -> dict:
    rows = list(_uptime_rows(user, period, website_id))
    total = len(rows)
    up = sum(1 for _, details, status in rows if _is_up(details, status))
    last_check = (
        CheckResult.objects.filter(
            scan__website__owner=user,
            category=CheckResult.Category.UPTIME,
            scan__status=Scan.Status.COMPLETED,
        )
        .order_by("-scan__created_at")
        .values_list("scan__created_at", flat=True)
        .first()
    )

    configs = MonitoringConfig.objects.filter(website__owner=user).select_related(
        "website"
    )
    if website_id is not None:
        configs = configs.filter(website_id=website_id)
    enabled = [config for config in configs if config.enabled]
    intervals = sorted({config.interval for config in enabled})
    interval = intervals[0] if len(intervals) == 1 else ("mixed" if intervals else None)

    websites = Website.objects.filter(owner=user)
    if website_id is not None:
        websites = websites.filter(pk=website_id)
    latest_scans = {
        scan.website_id: scan
        for scan in Scan.objects.filter(website__in=websites)
        .order_by("website_id", "-created_at")
        .distinct("website_id")
    }

    return {
        "monitored_websites": websites.count(),
        "enabled_websites": len(enabled),
        "healthy_websites": sum(
            1
            for website in websites
            if getattr(latest_scans.get(website.id), "health_status", None)
            == "healthy"
        ),
        "warning_websites": sum(
            1
            for website in websites
            if getattr(latest_scans.get(website.id), "health_status", None)
            == "warning"
        ),
        "critical_websites": sum(
            1
            for website in websites
            if getattr(latest_scans.get(website.id), "health_status", None)
            == "critical"
        ),
        "uptime_percent": round(up / total * 100, 2) if total else None,
        "uptime_checks": total,
        "failed_checks": total - up,
        "last_check_at": last_check.isoformat() if last_check else None,
        "interval": interval,
    }


def _websites(user, website_id: int | None) -> list[dict]:
    configs = (
        MonitoringConfig.objects.filter(website__owner=user)
        .select_related("website")
        .order_by("website__domain")
    )
    if website_id is not None:
        configs = configs.filter(website_id=website_id)

    websites = []
    for config in configs:
        latest = (
            Scan.objects.filter(website=config.website)
            .order_by("-created_at")
            .only("health_score", "health_status", "created_at", "completed_at")
            .first()
        )
        websites.append(
            {
                "id": config.website_id,
                "domain": config.website.domain,
                "enabled": config.enabled,
                "interval": config.interval,
                "last_scan_at": config.last_scan_at.isoformat()
                if config.last_scan_at
                else None,
                "next_scan_at": config.next_scan_at.isoformat()
                if config.next_scan_at
                else None,
                "consecutive_failures": config.consecutive_failures,
                "escalation_level": config.escalation_level,
                "health_score": latest.health_score if latest else None,
                "health_status": latest.health_status if latest else "neutral",
                "last_check_at": latest.created_at.isoformat() if latest else None,
            }
        )
    return websites


def _events(user, website_id: int | None, limit: int = 20) -> list[dict]:
    alerts = Alert.objects.filter(website__owner=user).select_related("website")
    if website_id is not None:
        alerts = alerts.filter(website_id=website_id)
    alerts = alerts.order_by("-created_at")[:limit]

    events: list[dict] = []
    for alert in alerts:
        events.append(
            {
                "id": f"alert-{alert.id}",
                "kind": "alert",
                "severity": alert.severity,
                "status": alert.status,
                "title": alert.title,
                "detail": f"{alert.website.domain} · {alert.message}",
                "occurred_at": alert.created_at.isoformat(),
            }
        )

    scans = Scan.objects.filter(
        website__owner=user,
        status__in=[
            Scan.Status.COMPLETED,
            Scan.Status.PARTIAL,
            Scan.Status.FAILED,
        ],
    ).select_related("website")
    if website_id is not None:
        scans = scans.filter(website_id=website_id)
    for scan in scans.order_by("-created_at")[:limit]:
        if scan.status == Scan.Status.FAILED:
            events.append(
                {
                    "id": f"scan-{scan.id}",
                    "kind": "scan",
                    "severity": "critical",
                    "status": scan.status,
                    "title": "Scan failed",
                    "detail": scan.failure_message
                    or f"{scan.website.domain} — no diagnostic message",
                    "occurred_at": scan.created_at.isoformat(),
                }
            )
        elif scan.status == Scan.Status.PARTIAL:
            events.append(
                {
                    "id": f"scan-{scan.id}",
                    "kind": "scan",
                    "severity": "warning",
                    "status": scan.status,
                    "title": "Scan incomplete",
                    "detail": scan.failure_message
                    or f"{scan.website.domain} — one or more scanners did not finish",
                    "occurred_at": scan.created_at.isoformat(),
                }
            )
        else:
            events.append(
                {
                    "id": f"scan-{scan.id}",
                    "kind": "scan",
                    "severity": scan.health_status,
                    "status": scan.status,
                    "title": (
                        f"Scan completed — {scan.health_score}/100"
                        if scan.health_score is not None
                        else "Scan completed"
                    ),
                    "detail": f"{scan.website.domain} · {scan.get_trigger_display()} scan",
                    "occurred_at": scan.created_at.isoformat(),
                }
            )

    events.sort(key=lambda event: event["occurred_at"], reverse=True)
    return events[:limit]


def build_overview(user, period_key: str | None, website_id: int | None) -> dict:
    period = resolve_period(period_key)
    return {
        "period": period.key,
        "from": period.start.isoformat(),
        "to": period.end.isoformat(),
        "website_id": website_id,
        "summary": _summary(user, period, website_id),
        "series": _series(user, period, website_id),
        "websites": _websites(user, website_id),
        "events": _events(user, website_id),
    }
