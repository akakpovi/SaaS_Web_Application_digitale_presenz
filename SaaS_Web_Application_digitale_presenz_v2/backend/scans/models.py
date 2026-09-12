from typing import Any
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class HealthStatus(models.TextChoices):
    HEALTHY = "healthy", "Healthy"
    WARNING = "warning", "Warning"
    CRITICAL = "critical", "Critical"
    NEUTRAL = "neutral", "Neutral"


class Scan(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class Trigger(models.TextChoices):
        MANUAL = "manual", "Manual"
        ONBOARDING = "onboarding", "Onboarding"
        MONITORING = "monitoring", "Monitoring"
        PUBLIC = "public", "Public"

    class ScanType(models.TextChoices):
        HEALTH = "health", "Health"
        SECURITY = "security", "Security"
        FULL = "full", "Full"

    website = models.ForeignKey(
        "websites.Website",
        on_delete=models.CASCADE,
        related_name="scans"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    trigger = models.CharField(max_length=16, choices=Trigger.choices, default=Trigger.MANUAL)
    scan_type = models.CharField(
        max_length=16,
        choices=ScanType.choices,
        default=ScanType.HEALTH,
        help_text="Type of scan: health (internal checks), security (external tools), or full."
    )
    health_score = models.PositiveSmallIntegerField(null=True, blank=True)
    health_status = models.CharField(
        max_length=12,
        choices=HealthStatus.choices,
        default=HealthStatus.NEUTRAL
    )
    failure_message = models.CharField(max_length=500, blank=True)

    # Progress tracking
    progress = models.PositiveSmallIntegerField(
        default=0,
        help_text="Overall scan progress, 0–100."
    )
    current_step = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Human-readable label of the currently executing scanner step."
    )
    steps = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Ordered list of scanner steps with status/progress for real-time feed. "
            "Format: [{key, label, status, progress, duration_ms, error}]"
        )
    )

    # Guest architecture fields
    is_guest = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True if performed by an unauthenticated visitor."
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
        help_text="Django session key of the guest visitor."
    )

    queued_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["website", "-created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["is_guest", "created_at"]),
            models.Index(fields=["session_key"]),
            models.Index(fields=["scan_type", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(health_score__isnull=True) | Q(health_score__gte=0, health_score__lte=100),
                name="scan_health_score_range",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=["pending", "queued", "running", "completed", "failed", "cancelled"]
                ),
                name="scan_status_valid",
            ),
        ]

    _TRANSITIONS = {
        Status.PENDING: {Status.QUEUED, Status.FAILED, Status.CANCELLED},
        Status.QUEUED: {Status.RUNNING, Status.FAILED, Status.CANCELLED},
        Status.RUNNING: {Status.COMPLETED, Status.FAILED, Status.CANCELLED},
        Status.COMPLETED: set(),
        Status.FAILED: set(),
        Status.CANCELLED: set(),
    }

    def transition_to(self, target: "Scan.Status", *, failure_message: str = "") -> None:
        if target == self.status:
            return
        if target not in self._TRANSITIONS.get(self.status, set()):
            raise ValidationError({"status": f"Cannot transition from {self.status} to {target}."})

        now = timezone.now()
        self.status = target
        if target == self.Status.QUEUED:
            self.queued_at = now
        if target == self.Status.RUNNING:
            self.started_at = now
        if target in {self.Status.COMPLETED, self.Status.FAILED, self.Status.CANCELLED}:
            self.completed_at = now
        if target == self.Status.FAILED:
            self.failed_at = now
            self.failure_message = failure_message[:500]
        self.full_clean()
        self.save()

    def update_progress(
        self,
        progress: int,
        current_step: str = "",
        *,
        save: bool = True,
    ) -> None:
        """Update scan progress (0–100) and optional current step label."""
        self.progress = max(0, min(100, progress))
        if current_step:
            self.current_step = current_step
        if save:
            self.save(update_fields=["progress", "current_step", "updated_at"])

    def update_step(self, key: str, **kwargs: Any) -> None:
        """Update a step entry in the ``steps`` JSON field by key."""
        steps = self.steps or []
        for step in steps:
            if step.get("key") == key:
                step.update(kwargs)
                break
        self.steps = steps
        self.save(update_fields=["steps", "updated_at"])

    @property
    def is_active(self) -> bool:
        return self.status in {self.Status.QUEUED, self.Status.RUNNING}

    @property
    def duration_seconds(self) -> int | None:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None


class CheckResult(models.Model):
    class Category(models.TextChoices):
        WEBSITE = "website", "Website"
        SSL = "ssl", "SSL"
        DNS = "dns", "DNS"
        EMAIL_SECURITY = "email_security", "Email Security"
        SECURITY_HEADERS = "security_headers", "Security Headers"
        PERFORMANCE = "performance", "Performance"
        UPTIME = "uptime", "Uptime"

    scan = models.ForeignKey(Scan, on_delete=models.CASCADE, related_name="check_results")
    category = models.CharField(max_length=32, choices=Category.choices)
    status = models.CharField(max_length=12, choices=HealthStatus.choices, default=HealthStatus.NEUTRAL)
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    summary = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    technical_details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category"]
        constraints = [
            models.UniqueConstraint(fields=["scan", "category"], name="unique_check_result_per_scan_category"),
            models.CheckConstraint(condition=Q(score__isnull=True) | Q(score__gte=0, score__lte=20), name="check_result_score_range"),
        ]
        indexes = [models.Index(fields=["scan", "category"]), models.Index(fields=["status"])]

    def clean(self) -> None:
        from .services.scoring import CHECK_WEIGHTS

        if self.category == self.Category.UPTIME:
            if self.score is not None:
                raise ValidationError({"score": "Uptime is tracked separately and cannot contribute to health score."})
            return
        if self.score is None:
            raise ValidationError({"score": "A weighted health check requires a score."})
        if self.score > CHECK_WEIGHTS[self.category]:
            raise ValidationError({"score": f"Score cannot exceed {CHECK_WEIGHTS[self.category]} for this category."})


class ScannerRun(models.Model):
    """Records the execution of a single scanner within a Scan."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        TIMEOUT = "timeout", "Timeout"
        CANCELLED = "cancelled", "Cancelled"
        UNAVAILABLE = "unavailable", "Unavailable"

    scan = models.ForeignKey(
        Scan,
        on_delete=models.CASCADE,
        related_name="scanner_runs",
    )
    scanner = models.CharField(
        max_length=64,
        help_text="Scanner name (e.g. 'nmap', 'ssl', 'dns').",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    exit_code = models.SmallIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    raw_output = models.TextField(blank=True, help_text="Truncated raw tool output for debugging.")
    metadata = models.JSONField(default=dict, blank=True, help_text="Scanner-specific metadata.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["scan", "scanner"]),
            models.Index(fields=["scanner", "status"]),
        ]

    def start(self) -> None:
        self.status = self.Status.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def finish(
        self,
        *,
        status: str,
        exit_code: int | None = None,
        error_message: str = "",
        raw_output: str = "",
        metadata: dict | None = None,
        duration_ms: int | None = None,
    ) -> None:
        now = timezone.now()
        self.status = status
        self.finished_at = now
        if duration_ms is not None:
            self.duration_ms = duration_ms
        elif self.started_at:
            self.duration_ms = int((now - self.started_at).total_seconds() * 1000)
        self.exit_code = exit_code
        self.error_message = error_message[:2000]
        # Truncate raw output to prevent huge DB rows.
        self.raw_output = raw_output[:50_000]
        if metadata:
            self.metadata = metadata
        self.save(update_fields=[
            "status", "finished_at", "duration_ms",
            "exit_code", "error_message", "raw_output", "metadata",
        ])


class Finding(models.Model):
    """A normalised security/health finding produced by a scanner."""

    class Severity(models.TextChoices):
        INFO = "info", "Info"
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        WARNING = "warning", "Warning"
        NOT_APPLICABLE = "not_applicable", "Not Applicable"
        UNKNOWN = "unknown", "Unknown"

    scanner_run = models.ForeignKey(
        ScannerRun,
        on_delete=models.CASCADE,
        related_name="findings",
    )
    category = models.CharField(
        max_length=32,
        help_text="Category matching CheckResult.Category (e.g. 'ssl', 'dns', 'security').",
    )
    check_code = models.CharField(
        max_length=128,
        help_text="Dot-separated check code, e.g. 'ssl.certificate_valid'.",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.INFO)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UNKNOWN)
    evidence = models.JSONField(default=dict, blank=True)
    detected_value = models.JSONField(null=True, blank=True)
    expected_value = models.JSONField(null=True, blank=True)
    recommendation = models.TextField(blank=True)
    reference_url = models.URLField(max_length=500, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-severity", "category", "check_code"]
        indexes = [
            models.Index(fields=["scanner_run", "category"]),
            models.Index(fields=["scanner_run", "severity"]),
            models.Index(fields=["scanner_run", "status"]),
            models.Index(fields=["check_code"]),
        ]
