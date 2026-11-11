"""Alert escalation logic."""

import logging
from alerts.models import Alert, AlertPreference

logger = logging.getLogger(__name__)


def compute_severity(
    base_severity: str,
    consecutive_failures: int,
    preferences: AlertPreference,
) -> str:
    """Escalate severity based on consecutive failures."""
    if base_severity == "critical":
        return Alert.Severity.CRITICAL

    if consecutive_failures >= preferences.consecutive_failures_critical:
        return Alert.Severity.CRITICAL

    return Alert.Severity.WARNING


def should_create_alert(alert_type: str, preferences: AlertPreference) -> bool:
    """Check if alert type is enabled in preferences."""
    mapping = {
        "ssl_invalid": "ssl_invalid_enabled",
        "ssl_expiring": "ssl_expiring_enabled",
        "ssl_expired": "ssl_expiring_enabled",
        "website_offline": "website_offline_enabled",
        "dns_problem": "dns_problem_enabled",
        "email_security": "email_security_enabled",
        "security_headers": "security_headers_enabled",
        "performance": "performance_enabled",
        "score_drop": "score_drop_enabled",
        "scan_failed": "scan_failed_enabled",
    }
    attr = mapping.get(alert_type)
    return getattr(preferences, attr, True) if attr else True
