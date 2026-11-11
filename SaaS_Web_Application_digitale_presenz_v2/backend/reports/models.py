import uuid
from django.conf import settings
from django.db import models
from websites.models import Website

User = settings.AUTH_USER_MODEL


class Report(models.Model):
    class Period(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        GENERATED = "generated", "Generated"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports")
    website = models.ForeignKey(
        Website, on_delete=models.CASCADE, related_name="reports"
    )

    period = models.CharField(
        max_length=10, choices=Period.choices, default=Period.MONTHLY
    )
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )

    # Scores
    current_score = models.IntegerField(null=True, blank=True)
    previous_score = models.IntegerField(null=True, blank=True)
    score_change = models.IntegerField(null=True, blank=True)

    # Summary data (JSON)
    check_breakdown = models.JSONField(default=dict)
    improvements = models.JSONField(default=list)
    problems = models.JSONField(default=list)
    recommendations = models.JSONField(default=list)
    score_history = models.JSONField(default=list)

    # Meta
    total_scans = models.IntegerField(default=0)
    generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_start"]
        indexes = [
            models.Index(fields=["user", "website", "-period_start"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["website", "period", "period_start"],
                name="unique_report_per_website_period",
            )
        ]
        verbose_name = "Report"

    def __str__(self) -> str:
        return f"Report({self.website.domain}, {self.period}, {self.period_start})"

    @property
    def score_trend(self) -> str:
        if self.score_change is None:
            return "neutral"
        if self.score_change > 0:
            return "up"
        if self.score_change < 0:
            return "down"
        return "stable"
