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

    class Trigger(models.TextChoices):
        MANUAL = "manual", "Manual"
        ONBOARDING = "onboarding", "Onboarding"
        MONITORING = "monitoring", "Monitoring"
        PUBLIC = "public", "Public"

    website = models.ForeignKey("websites.Website", on_delete=models.CASCADE, related_name="scans")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    trigger = models.CharField(max_length=16, choices=Trigger.choices, default=Trigger.MANUAL)
    health_score = models.PositiveSmallIntegerField(null=True, blank=True)
    health_status = models.CharField(max_length=12, choices=HealthStatus.choices, default=HealthStatus.NEUTRAL)
    failure_message = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["website", "-created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(health_score__isnull=True) | Q(health_score__gte=0, health_score__lte=100), name="scan_health_score_range"),
            models.CheckConstraint(condition=Q(status__in=["pending", "queued", "running", "completed", "failed"]), name="scan_status_valid"),
        ]

    _TRANSITIONS = {
        Status.PENDING: {Status.QUEUED, Status.FAILED},
        Status.QUEUED: {Status.RUNNING, Status.FAILED},
        Status.RUNNING: {Status.COMPLETED, Status.FAILED},
        Status.COMPLETED: set(),
        Status.FAILED: set(),
    }

    def transition_to(self, target: "Scan.Status", *, failure_message: str = "") -> None:
        if target == self.status:
            return
        if target not in self._TRANSITIONS[self.status]:
            raise ValidationError({"status": f"Cannot transition from {self.status} to {target}."})

        now = timezone.now()
        self.status = target
        if target == self.Status.RUNNING:
            self.started_at = now
        if target in {self.Status.COMPLETED, self.Status.FAILED}:
            self.completed_at = now
        if target == self.Status.FAILED:
            self.failure_message = failure_message[:500]
        self.full_clean()
        self.save()


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
