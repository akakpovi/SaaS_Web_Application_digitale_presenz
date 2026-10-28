import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from scans.models import CheckResult, Finding, Scan


class AIRecommendationRun(models.Model):
    """One idempotent AI recommendation generation for a scan.

    ``input_hash`` captures the prompt version, the ordered model list and the
    scan evidence.  The unique constraint on ``(scan, input_hash)`` guarantees
    that replaying the same input never creates a second run.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scan = models.ForeignKey(
        Scan,
        on_delete=models.CASCADE,
        related_name="ai_recommendation_runs",
    )
    input_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 of the canonical prompt input and model list.",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    model_used = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="AKA model that produced the persisted recommendations.",
    )
    attempts = models.PositiveSmallIntegerField(
        default=0,
        help_text="Number of provider attempts claimed for this run.",
    )
    error_code = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Sanitised provider error code from the last failed attempt.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["scan", "input_hash"],
                name="unique_ai_run_per_scan_input",
            ),
        ]
        indexes = [
            models.Index(fields=["scan", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]
        verbose_name = "AI recommendation run"

    def __str__(self) -> str:
        return (
            f"AIRecommendationRun({self.scan_id}, {self.status}, "
            f"{self.model_used or 'no-model'})"
        )


class AIRecommendation(models.Model):
    """A validated recommendation tied to exactly one scan check or finding."""

    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        ACCEPTED = "accepted", "Accepted"
        DISMISSED = "dismissed", "Dismissed"

    class Effort(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class Priority(models.TextChoices):
        CRITICAL = "critical", "Critical"
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        AIRecommendationRun,
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    finding = models.ForeignKey(
        Finding,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ai_recommendations",
    )
    check_result = models.ForeignKey(
        CheckResult,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ai_recommendations",
    )
    title = models.CharField(max_length=255)
    summary = models.TextField()
    action = models.TextField()
    effort = models.CharField(
        max_length=8,
        choices=Effort.choices,
        default=Effort.MEDIUM,
    )
    priority = models.CharField(
        max_length=8,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Model confidence between 0 and 1.",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PROPOSED,
    )
    accepted_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_ai_recommendations",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    dismissed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dismissed_ai_recommendations",
    )
    dismissed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(finding__isnull=False, check_result__isnull=True)
                    | Q(finding__isnull=True, check_result__isnull=False)
                ),
                name="ai_recommendation_one_target",
            ),
            models.CheckConstraint(
                condition=Q(confidence__gte=0.0, confidence__lte=1.0),
                name="ai_recommendation_confidence_range",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["proposed", "accepted", "dismissed"]),
                name="ai_recommendation_status_valid",
            ),
        ]
        verbose_name = "AI recommendation"

    def __str__(self) -> str:
        target = self.finding_id or self.check_result_id
        return f"AIRecommendation({self.title!r}, target={target})"

    def accept(self, user) -> None:
        """Record a user's acceptance; idempotent for the same state."""
        if self.status == self.Status.ACCEPTED:
            return
        self.status = self.Status.ACCEPTED
        self.accepted_by = user
        self.accepted_at = timezone.now()
        self.dismissed_by = None
        self.dismissed_at = None
        self.save(
            update_fields=[
                "status",
                "accepted_by",
                "accepted_at",
                "dismissed_by",
                "dismissed_at",
                "updated_at",
            ]
        )

    def dismiss(self, user) -> None:
        """Record a user's dismissal; idempotent for the same state."""
        if self.status == self.Status.DISMISSED:
            return
        self.status = self.Status.DISMISSED
        self.dismissed_by = user
        self.dismissed_at = timezone.now()
        self.accepted_by = None
        self.accepted_at = None
        self.save(
            update_fields=[
                "status",
                "dismissed_by",
                "dismissed_at",
                "accepted_by",
                "accepted_at",
                "updated_at",
            ]
        )


class SecurityFinding(models.Model):
    """A normalised security finding owned by exactly one organization.

    Scanners (ZAP, Nuclei, the built-in checks) produce very different
    payloads.  This model is the single, tenant-scoped shape the AI advisor
    reads: one row per vulnerability on one asset.

    ``organization`` is stored explicitly (not only reached through
    ``asset.organization``) so every query can filter on the tenant without a
    join, and so a finding can never be served across organizations by
    accident.  ``save()`` still enforces ``asset.organization ==
    organization``: a mismatch is a programming error, not a data state.

    ``proof_or_payload`` holds raw evidence (HTTP responses, payloads).  It is
    untrusted data: it is bounded before being sent to the model and never
    logged.
    """

    class Severity(models.TextChoices):
        CRITICAL = "critical", "Critical"
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"
        INFO = "info", "Info"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="security_findings",
    )
    asset = models.ForeignKey(
        "websites.Website",
        on_delete=models.CASCADE,
        related_name="security_findings",
        help_text="Website (domain) the finding was detected on.",
    )
    scanner_source = models.CharField(
        max_length=32,
        help_text="Scanner that produced the finding, e.g. 'zap' or 'nuclei'.",
    )
    vulnerability_name = models.CharField(max_length=255)
    severity = models.CharField(
        max_length=16,
        choices=Severity.choices,
        default=Severity.MEDIUM,
        db_index=True,
    )
    description = models.TextField(blank=True, default="")
    proof_or_payload = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    detected_at = models.DateTimeField(default=timezone.now, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-detected_at"]
        constraints = [
            # Identity used by the ingestion pipeline: one row per
            # vulnerability per asset per scanner.  It also makes a duplicate
            # insert from two concurrent uploads impossible at the DB level.
            models.UniqueConstraint(
                fields=["asset", "scanner_source", "vulnerability_name"],
                name="sec_finding_unique_asset_source_name",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "status", "severity"],
                name="sec_finding_org_status_sev_idx",
            ),
            models.Index(
                fields=["asset", "status"],
                name="sec_finding_asset_status_idx",
            ),
            models.Index(
                fields=["organization", "detected_at"],
                name="sec_finding_org_detected_idx",
            ),
        ]
        verbose_name = "Security finding"

    def __str__(self) -> str:
        # No proof, payload or host header: the label may be logged safely.
        return (
            f"{self.severity}:{self.vulnerability_name}"
            f"@{self.asset_id} ({self.organization_id})"
        )

    def clean(self) -> None:
        super().clean()
        self._validate_asset_tenant()

    def _validate_asset_tenant(self) -> None:
        asset = self.asset
        if asset is None:
            return
        if asset.is_guest:
            raise ValidationError(
                {"asset": "A guest scan asset cannot hold organization findings."}
            )
        if asset.organization_id is None:
            raise ValidationError(
                {"asset": "The asset must belong to an organization."}
            )
        if self.organization_id and asset.organization_id != self.organization_id:
            raise ValidationError(
                {"asset": "The asset belongs to another organization."}
            )

    def save(self, *args, **kwargs):
        # ``save()`` is called directly by ingestion code and fixtures, which do
        # not run ``full_clean()``: the tenant invariant is checked here.
        self._validate_asset_tenant()
        super().save(*args, **kwargs)

    def resolve(self, when=None) -> None:
        """Mark the finding resolved; idempotent."""
        if self.status == self.Status.RESOLVED:
            return
        self.status = self.Status.RESOLVED
        self.resolved_at = when or timezone.now()
        self.save(update_fields=["status", "resolved_at", "updated_at"])
