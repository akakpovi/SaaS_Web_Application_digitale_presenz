import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from websites.models import Website

User = settings.AUTH_USER_MODEL


class AlertPreference(models.Model):
    class DigestFrequency(models.TextChoices):
        IMMEDIATE = "immediate", "Immediate"
        HOURLY    = "hourly",    "Hourly digest"
        DAILY     = "daily",     "Daily digest"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="alert_preferences"
    )

    # Activation par type
    ssl_expiring_enabled      = models.BooleanField(default=True)
    ssl_invalid_enabled       = models.BooleanField(default=True)
    website_offline_enabled   = models.BooleanField(default=True)
    dns_problem_enabled       = models.BooleanField(default=True)
    email_security_enabled    = models.BooleanField(default=True)
    security_headers_enabled  = models.BooleanField(default=True)
    performance_enabled       = models.BooleanField(default=True)
    score_drop_enabled        = models.BooleanField(default=True)
    scan_failed_enabled       = models.BooleanField(default=True)

    # Seuils
    ssl_expiry_warning_days       = models.IntegerField(default=30)
    ssl_expiry_critical_days      = models.IntegerField(default=7)
    score_drop_threshold          = models.IntegerField(default=10)
    consecutive_failures_critical = models.IntegerField(default=3)

    # Digest / quiet hours
    digest_frequency  = models.CharField(
        max_length=10,
        choices=DigestFrequency.choices,
        default=DigestFrequency.IMMEDIATE,
    )
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end   = models.TimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Alert Preference"

    def __str__(self) -> str:
        return f"AlertPreference({self.user.email})"

    def is_in_quiet_hours(self, now: timezone.datetime | None = None) -> bool:
        if not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        now = now or timezone.now()
        current_time = now.astimezone(timezone.get_current_timezone()).time()
        start, end = self.quiet_hours_start, self.quiet_hours_end
        if start <= end:
            return start <= current_time <= end
        return current_time >= start or current_time <= end


class MuteWindow(models.Model):
    class Reason(models.TextChoices):
        MAINTENANCE = "maintenance", "Maintenance"
        DEPLOYMENT  = "deployment",  "Deployment"
        MIGRATION   = "migration",   "Migration"
        OTHER       = "other",       "Other"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="mute_windows"
    )
    websites = models.ManyToManyField(
        Website,
        related_name="mute_windows",
        blank=True,
        help_text="Empty = all user's websites",
    )
    start_at  = models.DateTimeField()
    end_at    = models.DateTimeField()
    reason    = models.CharField(
        max_length=20, choices=Reason.choices, default=Reason.MAINTENANCE
    )
    note      = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_at"]
        verbose_name = "Mute Window"

    def __str__(self) -> str:
        return f"MuteWindow({self.user.email}, {self.start_at} → {self.end_at})"

    def is_currently_muting(self, now: timezone.datetime | None = None) -> bool:
        now = now or timezone.now()
        return self.is_active and self.start_at <= now <= self.end_at


class Alert(models.Model):
    class Severity(models.TextChoices):
        INFO     = "info",     "Info"
        WARNING  = "warning",  "Warning"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        FIRING       = "firing",       "Firing"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED     = "resolved",     "Resolved"

    class AlertType(models.TextChoices):
        SSL_EXPIRING        = "ssl_expiring",        "SSL Expiring"
        SSL_INVALID         = "ssl_invalid",         "SSL Invalid"
        SSL_EXPIRED         = "ssl_expired",         "SSL Expired"
        WEBSITE_OFFLINE     = "website_offline",     "Website Offline"
        DNS_PROBLEM         = "dns_problem",         "DNS Problem"
        EMAIL_SECURITY      = "email_security",      "Email Security"
        SECURITY_HEADERS    = "security_headers",    "Security Headers"
        PERFORMANCE         = "performance",         "Performance"
        SCORE_DROP          = "score_drop",          "Score Drop"
        SCAN_FAILED         = "scan_failed",         "Scan Failed"
        AI_RUN_REAPED       = "ai_run_reaped",       "AI Run Reaped"
        MONITORING_DISABLED = "monitoring_disabled", "Monitoring Disabled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user    = models.ForeignKey(User, on_delete=models.CASCADE, related_name="alerts")
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name="alerts")
    scan    = models.ForeignKey(
        "scans.Scan", on_delete=models.SET_NULL, null=True, blank=True, related_name="alerts"
    )

    alert_type = models.CharField(max_length=30, choices=AlertType.choices)
    severity   = models.CharField(max_length=10, choices=Severity.choices)
    status     = models.CharField(
        max_length=15, choices=Status.choices, default=Status.FIRING
    )

    title    = models.CharField(max_length=255)
    message  = models.TextField()
    metadata = models.JSONField(default=dict)
    notification_channels_sent = models.JSONField(default=list)

    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="acknowledged_alerts",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["website", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]
        verbose_name = "Alert"

    def __str__(self) -> str:
        return f"Alert({self.alert_type}, {self.severity}, {self.website.domain})"

    def acknowledge(self, user) -> None:
        self.status = self.Status.ACKNOWLEDGED
        self.acknowledged_at = timezone.now()
        self.acknowledged_by = user
        self.save(update_fields=["status", "acknowledged_at", "acknowledged_by", "updated_at"])

    def resolve(self) -> None:
        self.status = self.Status.RESOLVED
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolved_at", "updated_at"])


class AlertRule(models.Model):
    class Metric(models.TextChoices):
        HEALTH_SCORE       = "health_score",       "Health Score"
        SSL_DAYS_REMAINING = "ssl_days_remaining", "SSL Days Remaining"
        LOAD_TIME_MS       = "load_time_ms",       "Load Time (ms)"
        PAGE_SIZE_KB       = "page_size_kb",       "Page Size (KB)"

    class Operator(models.TextChoices):
        GT  = "gt",  "Greater than"
        LT  = "lt",  "Less than"
        GTE = "gte", "Greater than or equal"
        LTE = "lte", "Less than or equal"
        EQ  = "eq",  "Equal"

    class Severity(models.TextChoices):
        WARNING  = "warning",  "Warning"
        CRITICAL = "critical", "Critical"

    user    = models.ForeignKey(User, on_delete=models.CASCADE, related_name="alert_rules")
    website = models.ForeignKey(
        Website, on_delete=models.CASCADE, null=True, blank=True, related_name="alert_rules"
    )
    name      = models.CharField(max_length=100)
    metric    = models.CharField(max_length=25, choices=Metric.choices)
    operator  = models.CharField(max_length=5, choices=Operator.choices)
    threshold = models.FloatField()
    severity  = models.CharField(max_length=10, choices=Severity.choices)
    enabled   = models.BooleanField(default=True)
    cooldown_minutes  = models.IntegerField(default=60)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Alert Rule"

    def __str__(self) -> str:
        return f"AlertRule({self.name}, {self.metric} {self.operator} {self.threshold})"

    def is_in_cooldown(self, now: timezone.datetime | None = None) -> bool:
        if not self.last_triggered_at:
            return False
        now = now or timezone.now()
        from datetime import timedelta
        return now < self.last_triggered_at + timedelta(minutes=self.cooldown_minutes)

    def evaluate(self, value: float) -> bool:
        ops = {
            "gt": lambda v, t: v > t,
            "lt": lambda v, t: v < t,
            "gte": lambda v, t: v >= t,
            "lte": lambda v, t: v <= t,
            "eq": lambda v, t: v == t,
        }
        fn = ops.get(self.operator)
        return fn(value, self.threshold) if fn else False
