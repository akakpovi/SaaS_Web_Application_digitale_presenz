import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def report_scan_issue(self, scan_id: int) -> dict:
    """Alert the owner when a scan failed or only partially covered the site.

    A failed or incomplete scan is an incident of its own: the absence of a
    finding does **not** prove the site is healthy, and the owner must be told
    that coverage is missing.  This task never resolves another alert — only a
    later completed scan can do that.
    """
    from alerts.models import Alert, AlertPreference, MuteWindow
    from core.escalation import should_create_alert
    from notifications.dispatcher import dispatch_alert
    from scans.models import Scan

    try:
        scan = Scan.objects.select_related("website", "website__owner").get(id=scan_id)
    except Scan.DoesNotExist:
        logger.error("report_scan_issue: Scan %s not found", scan_id)
        return {"error": "scan_not_found"}

    if scan.status not in (Scan.Status.FAILED, Scan.Status.PARTIAL):
        return {"skipped": "not_an_issue"}

    website = scan.website
    user = website.owner
    preferences, _ = AlertPreference.objects.get_or_create(user=user)
    if not should_create_alert("scan_failed", preferences):
        return {"skipped": "preference_disabled"}

    now = timezone.now()
    active_mutes = MuteWindow.objects.filter(
        user=user, is_active=True, start_at__lte=now, end_at__gte=now
    )
    if (
        active_mutes.filter(websites__isnull=True).exists()
        or active_mutes.filter(websites=website).exists()
    ):
        return {"skipped": "mute_window"}

    already_firing = Alert.objects.filter(
        website=website,
        alert_type=Alert.AlertType.SCAN_FAILED,
        status=Alert.Status.FIRING,
    ).exists()
    if already_firing:
        # Keep the existing alert but attach the latest scan so the UI links to
        # the run that just failed instead of an older one.
        Alert.objects.filter(
            website=website,
            alert_type=Alert.AlertType.SCAN_FAILED,
            status=Alert.Status.FIRING,
        ).update(scan=scan, updated_at=now)
        return {"created": 0, "updated": 1}

    partial = scan.status == Scan.Status.PARTIAL
    config = getattr(website, "monitoring_config", None)
    consecutive_failures = config.consecutive_failures if config else 0
    # A single incomplete run is a warning; repeated incomplete runs mean the
    # coverage has been broken for several cycles and deserve a critical alert.
    severity = (
        Alert.Severity.CRITICAL
        if not partial or consecutive_failures >= 2
        else Alert.Severity.WARNING
    )
    title = (
        f"Scan coverage incomplete for {website.domain}"
        if partial
        else f"Scan failed for {website.domain}"
    )
    message = scan.failure_message or (
        "The last scan did not cover every required check. "
        "Missing results are not proof that the site is healthy."
    )

    alert = Alert.objects.create(
        user=user,
        website=website,
        scan=scan,
        alert_type=Alert.AlertType.SCAN_FAILED,
        severity=severity,
        title=title,
        message=message,
        metadata={"scan_id": scan.id, "coverage": scan.status},
    )
    dispatch_alert(alert)
    logger.info(
        "report_scan_issue: alert %s created for scan %s (%s)",
        alert.id,
        scan_id,
        scan.status,
    )
    return {"created": 1, "alert_id": str(alert.id)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def detect_alerts(self, scan_id: int) -> dict:
    """Analyse a completed scan and create alerts as needed."""
    from alerts.models import Alert, AlertPreference, MuteWindow
    from core.escalation import compute_severity, should_create_alert
    from notifications.dispatcher import dispatch_alert
    from scans.models import CheckResult, Scan

    try:
        scan = Scan.objects.select_related("website", "website__owner").get(id=scan_id)
        if scan.status != Scan.Status.COMPLETED:
            # Only a completed scan can create findings-based alerts or prove
            # that a previous incident is over.  A stale/duplicated message
            # for an incomplete run must be a no-op.
            logger.info(
                "detect_alerts skipped: scan %s status=%s", scan_id, scan.status
            )
            return {"skipped": "not_completed"}
        website = scan.website
        user = website.owner
        now = timezone.now()

        preferences, _ = AlertPreference.objects.get_or_create(user=user)
        config = getattr(website, "monitoring_config", None)
        consecutive_failures = config.consecutive_failures if config else 0

        # Mute window guard
        active_mutes = MuteWindow.objects.filter(
            user=user, is_active=True, start_at__lte=now, end_at__gte=now
        )
        if (
            active_mutes.filter(websites__isnull=True).exists()
            or active_mutes.filter(websites=website).exists()
        ):
            logger.info("detect_alerts skipped — mute window active for %s", website.domain)
            return {"skipped": "mute_window"}

        alerts_to_fire: list[Alert] = []

        # 1. SSL checks
        ssl_result = CheckResult.objects.filter(scan=scan, category="ssl").first()
        if ssl_result:
            details = ssl_result.technical_details or {}
            days_remaining = details.get("days_until_expiry", 999)
            ssl_valid = details.get("is_valid", True)

            if not ssl_valid and should_create_alert("ssl_invalid", preferences):
                alerts_to_fire.append(_build_alert(
                    user, website, scan,
                    Alert.AlertType.SSL_INVALID, Alert.Severity.CRITICAL,
                    f"SSL certificate invalid for {website.domain}",
                    details.get("error", "SSL certificate is invalid."),
                ))
            elif isinstance(days_remaining, (int, float)):
                if days_remaining <= preferences.ssl_expiry_critical_days and should_create_alert("ssl_expired", preferences):
                    sev = compute_severity("critical", consecutive_failures, preferences)
                    alerts_to_fire.append(_build_alert(
                        user, website, scan,
                        Alert.AlertType.SSL_EXPIRED, sev,
                        f"SSL certificate expiring critically soon for {website.domain}",
                        f"SSL certificate expires in {days_remaining} days.",
                        {"days_remaining": days_remaining},
                    ))
                elif days_remaining <= preferences.ssl_expiry_warning_days and should_create_alert("ssl_expiring", preferences):
                    alerts_to_fire.append(_build_alert(
                        user, website, scan,
                        Alert.AlertType.SSL_EXPIRING, Alert.Severity.WARNING,
                        f"SSL certificate expiring for {website.domain}",
                        f"SSL certificate expires in {days_remaining} days.",
                        {"days_remaining": days_remaining},
                    ))

        # 2. Website offline
        web_result = CheckResult.objects.filter(scan=scan, category="website").first()
        if web_result and web_result.status == "critical" and should_create_alert("website_offline", preferences):
            sev = compute_severity("critical", consecutive_failures, preferences)
            alerts_to_fire.append(_build_alert(
                user, website, scan,
                Alert.AlertType.WEBSITE_OFFLINE, sev,
                f"{website.domain} is offline or unreachable",
                web_result.summary,
            ))

        # 3. DNS problem
        dns_result = CheckResult.objects.filter(scan=scan, category="dns").first()
        if dns_result and dns_result.status == "critical" and should_create_alert("dns_problem", preferences):
            sev = compute_severity("critical", consecutive_failures, preferences)
            alerts_to_fire.append(_build_alert(
                user, website, scan,
                Alert.AlertType.DNS_PROBLEM, sev,
                f"DNS problem detected for {website.domain}",
                dns_result.summary,
            ))

        # 4. E-mail authentication (SPF/DKIM/DMARC)
        email_result = CheckResult.objects.filter(scan=scan, category="email_security").first()
        if (
            email_result
            and email_result.status == "critical"
            and should_create_alert("email_security", preferences)
        ):
            sev = compute_severity("warning", consecutive_failures, preferences)
            alerts_to_fire.append(_build_alert(
                user, website, scan,
                Alert.AlertType.EMAIL_SECURITY, sev,
                f"E-mail authentication issues for {website.domain}",
                email_result.summary,
                email_result.technical_details,
            ))

        # 5. Security headers
        hdr_result = CheckResult.objects.filter(scan=scan, category="security_headers").first()
        if hdr_result and hdr_result.status == "critical" and should_create_alert("security_headers", preferences):
            sev = compute_severity("warning", consecutive_failures, preferences)
            alerts_to_fire.append(_build_alert(
                user, website, scan,
                Alert.AlertType.SECURITY_HEADERS, sev,
                f"Security headers issues on {website.domain}",
                hdr_result.summary,
            ))

        # 5. Performance
        perf_result = CheckResult.objects.filter(scan=scan, category="performance").first()
        if perf_result and perf_result.status == "critical" and should_create_alert("performance", preferences):
            sev = compute_severity("warning", consecutive_failures, preferences)
            alerts_to_fire.append(_build_alert(
                user, website, scan,
                Alert.AlertType.PERFORMANCE, sev,
                f"Performance issues detected for {website.domain}",
                perf_result.summary,
                perf_result.technical_details,
            ))

        # 6. Score drop
        if scan.health_score is not None and should_create_alert("score_drop", preferences):
            prev = (
                Scan.objects.filter(website=website, status=Scan.Status.COMPLETED)
                .exclude(id=scan.id)
                .order_by("-created_at")
                .first()
            )
            if prev and prev.health_score is not None:
                drop = prev.health_score - scan.health_score
                if drop >= preferences.score_drop_threshold:
                    sev = compute_severity("warning", consecutive_failures, preferences)
                    alerts_to_fire.append(_build_alert(
                        user, website, scan,
                        Alert.AlertType.SCORE_DROP, sev,
                        f"Health score dropped for {website.domain}",
                        f"Score dropped from {prev.health_score} to {scan.health_score} (-{drop} points).",
                        {"previous_score": prev.health_score, "current_score": scan.health_score, "drop": drop},
                    ))

        # Save + dispatch (with deduplication)
        created = 0
        for alert in alerts_to_fire:
            already_firing = Alert.objects.filter(
                website=website, alert_type=alert.alert_type, status=Alert.Status.FIRING
            ).exists()
            if already_firing:
                continue
            alert.save()
            dispatch_alert(alert)
            created += 1

        # Auto-resolve
        resolved = _auto_resolve(scan, website)

        return {"created": created, "resolved": resolved}

    except Scan.DoesNotExist:
        logger.error("detect_alerts: Scan %s not found", scan_id)
        return {"error": "scan_not_found"}
    except Exception as exc:
        logger.exception("detect_alerts failed for scan %s", scan_id)
        raise self.retry(exc=exc)


def _build_alert(user, website, scan, alert_type, severity, title, message, metadata=None):
    from alerts.models import Alert
    return Alert(
        user=user, website=website, scan=scan,
        alert_type=alert_type, severity=severity,
        title=title, message=message, metadata=metadata or {},
    )


def _auto_resolve(scan, website) -> int:
    from alerts.models import Alert
    from scans.models import CheckResult, Scan

    # Recovery can only be proven by a *completed* scan.  A partial or failed
    # run is never allowed to resolve anything, even if this helper is invoked
    # directly by a caller.
    if scan.status != Scan.Status.COMPLETED:
        return 0

    resolved = 0
    check_results = {cr.category: cr for cr in CheckResult.objects.filter(scan=scan)}

    for alert in Alert.objects.filter(website=website, status=Alert.Status.FIRING):
        should_resolve = False

        if alert.alert_type == Alert.AlertType.WEBSITE_OFFLINE:
            cr = check_results.get("website")
            if cr and cr.status != "critical":
                should_resolve = True
        elif alert.alert_type in (Alert.AlertType.SSL_EXPIRING, Alert.AlertType.SSL_EXPIRED, Alert.AlertType.SSL_INVALID):
            cr = check_results.get("ssl")
            if cr and cr.status in ("healthy", "warning"):
                should_resolve = True
        elif alert.alert_type == Alert.AlertType.DNS_PROBLEM:
            cr = check_results.get("dns")
            if cr and cr.status != "critical":
                should_resolve = True
        elif alert.alert_type == Alert.AlertType.EMAIL_SECURITY:
            cr = check_results.get("email_security")
            if cr and cr.status != "critical":
                should_resolve = True
        elif alert.alert_type == Alert.AlertType.SECURITY_HEADERS:
            cr = check_results.get("security_headers")
            if cr and cr.status != "critical":
                should_resolve = True
        elif alert.alert_type == Alert.AlertType.PERFORMANCE:
            cr = check_results.get("performance")
            if cr and cr.status != "critical":
                should_resolve = True
        elif alert.alert_type == Alert.AlertType.SCORE_DROP:
            # A drop is recovered once the score is back at (or above) the
            # value it had when the alert fired.
            baseline = alert.metadata.get("current_score")
            if (
                isinstance(baseline, (int, float))
                and scan.health_score is not None
                and scan.health_score >= baseline
            ):
                should_resolve = True
        elif alert.alert_type == Alert.AlertType.SCAN_FAILED:
            # Only reached from a completed scan (this task is not queued for
            # failed/partial runs): the coverage incident is over.
            should_resolve = True

        if should_resolve:
            alert.resolve()
            resolved += 1

    return resolved


@shared_task
def cleanup_old_alerts() -> dict:
    from alerts.models import Alert
    cutoff = timezone.now() - timezone.timedelta(days=90)
    deleted, _ = Alert.objects.filter(
        status=Alert.Status.RESOLVED, resolved_at__lt=cutoff
    ).delete()
    logger.info("cleanup_old_alerts: deleted %d old alerts", deleted)
    return {"deleted": deleted}
