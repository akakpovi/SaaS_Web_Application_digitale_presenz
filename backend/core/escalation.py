from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alerts.models import AlertPreference


def compute_severity(
    check_severity: str,
    consecutive_failures: int,
    preferences: "AlertPreference",
) -> str:
    """
    Determine alert severity.
    - critical check → always CRITICAL
    - consecutive_failures >= threshold → CRITICAL
    - otherwise → WARNING or INFO
    """
    if check_severity == "critical":
        return "critical"
    threshold = getattr(preferences, "consecutive_failures_critical", 3)
    if consecutive_failures >= threshold:
        return "critical"
    if check_severity == "warning" or consecutive_failures >= 1:
        return "warning"
    return "info"


def should_create_alert(
    alert_type: str,
    preferences: "AlertPreference",
) -> bool:
    """Check user preferences to determine if this alert type is enabled."""
    TYPE_PREF_MAP = {
        "ssl_expiring":     "ssl_expiring_enabled",
        "ssl_invalid":      "ssl_invalid_enabled",
        "ssl_expired":      "ssl_expiring_enabled",
        "website_offline":  "website_offline_enabled",
        "dns_problem":      "dns_problem_enabled",
        "email_security":   "email_security_enabled",
        "security_headers": "security_headers_enabled",
        "performance":      "performance_enabled",
        "score_drop":       "score_drop_enabled",
        "scan_failed":      "scan_failed_enabled",
    }
    pref_field = TYPE_PREF_MAP.get(alert_type)
    if pref_field is None:
        return True
    return bool(getattr(preferences, pref_field, True))
