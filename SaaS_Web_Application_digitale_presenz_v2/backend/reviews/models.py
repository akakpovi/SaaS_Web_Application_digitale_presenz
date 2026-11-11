import uuid
from django.conf import settings
from django.db import models
from websites.models import Website

User = settings.AUTH_USER_MODEL


class ReviewSource(models.Model):
    class Provider(models.TextChoices):
        GOOGLE = "google", "Google"
        TRUSTPILOT = "trustpilot", "Trustpilot"
        TRIPADVISOR = "tripadvisor", "TripAdvisor"
        MANUAL = "manual", "Manual"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="review_sources"
    )
    website = models.ForeignKey(
        Website, on_delete=models.CASCADE, related_name="review_sources"
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    name = models.CharField(max_length=100)
    config = models.JSONField(
        default=dict, help_text="Provider-specific config (place_id, etc.)"
    )
    enabled = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider", "name"]
        verbose_name = "Review Source"

    def __str__(self) -> str:
        return f"ReviewSource({self.provider}, {self.website.domain})"


class Review(models.Model):
    class Sentiment(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEUTRAL = "neutral", "Neutral"
        NEGATIVE = "negative", "Negative"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(
        ReviewSource, on_delete=models.CASCADE, related_name="reviews"
    )
    external_id = models.CharField(max_length=255, blank=True)
    author_name = models.CharField(max_length=150, blank=True)
    author_photo = models.URLField(blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    text = models.TextField(blank=True)
    sentiment = models.CharField(
        max_length=10, choices=Sentiment.choices, default=Sentiment.NEUTRAL
    )
    language = models.CharField(max_length=10, blank=True)
    is_approved = models.BooleanField(default=False)
    review_date = models.DateTimeField(null=True, blank=True)
    raw_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-review_date"]
        indexes = [
            models.Index(fields=["source", "-review_date"]),
            models.Index(fields=["is_approved"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=models.Q(external_id__gt=""),
                name="unique_review_external_id",
            )
        ]
        verbose_name = "Review"

    def __str__(self) -> str:
        return f"Review({self.source.provider}, {self.rating}★, {self.author_name})"


class ResponseDraft(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        SENT = "sent", "Sent"

    review = models.OneToOneField(
        Review, on_delete=models.CASCADE, related_name="response_draft"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="response_drafts"
    )
    content = models.TextField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Response Draft"

    def __str__(self) -> str:
        return f"ResponseDraft({self.review_id}, {self.status})"


class ReviewSentiment(models.Model):
    review = models.OneToOneField(
        Review, on_delete=models.CASCADE, related_name="sentiment_details"
    )
    confidence = models.FloatField(default=0.0)
    emotions = models.JSONField(default=dict, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    language_detected = models.CharField(max_length=10, default="fr")
    model_version = models.CharField(max_length=50, default="rule-based-v1")
    analyzed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Review Sentiment"

    def __str__(self) -> str:
        return f"Sentiment({self.review_id}, conf={self.confidence})"


class ReviewImportJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="review_imports"
    )
    source = models.ForeignKey(
        ReviewSource, on_delete=models.CASCADE, related_name="import_jobs"
    )
    file = models.FileField(upload_to="review_imports/%Y/%m/")
    file_type = models.CharField(
        max_length=5, choices=[("csv", "CSV"), ("json", "JSON")]
    )
    total_rows = models.PositiveIntegerField(default=0)
    imported_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Review Import Job"

    def __str__(self) -> str:
        return f"ImportJob({self.id}, {self.status})"
