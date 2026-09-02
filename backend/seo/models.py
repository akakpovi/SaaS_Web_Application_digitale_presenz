import uuid
from django.db import models
from websites.models import Website

class SEOAudit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name="seo_audits")
    overall_score = models.PositiveSmallIntegerField(default=0)
    technical_score = models.PositiveSmallIntegerField(default=0)
    content_score = models.PositiveSmallIntegerField(default=0)
    mobile_score = models.PositiveSmallIntegerField(default=0)
    meta_tags = models.JSONField(default=dict, blank=True)
    robots_txt = models.CharField(max_length=50, default="unknown")
    sitemap = models.CharField(max_length=50, default="unknown")
    issues = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["website", "-created_at"])]

class Keyword(models.Model):
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name="seo_keywords")
    term = models.CharField(max_length=255)
    country = models.CharField(max_length=2, default="FR")
    search_volume = models.PositiveIntegerField(null=True, blank=True)
    difficulty = models.PositiveSmallIntegerField(null=True, blank=True)
    current_rank = models.PositiveIntegerField(null=True, blank=True)
    previous_rank = models.PositiveIntegerField(null=True, blank=True)
    tracked = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["website", "term", "country"], name="unique_keyword_per_site")]

class Backlink(models.Model):
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name="seo_backlinks")
    source_url = models.URLField(max_length=2048)
    target_url = models.URLField(max_length=2048)
    anchor_text = models.CharField(max_length=500, blank=True)
    domain_authority = models.PositiveSmallIntegerField(default=0)
    is_dofollow = models.BooleanField(default=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["website", "-domain_authority"])]
