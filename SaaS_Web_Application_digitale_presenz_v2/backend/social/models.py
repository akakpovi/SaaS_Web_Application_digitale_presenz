from django.db import models
from websites.models import Website


class SocialProfile(models.Model):
    class Provider(models.TextChoices):
        FACEBOOK = "facebook", "Facebook"
        INSTAGRAM = "instagram", "Instagram"
        TWITTER = "twitter", "Twitter/X"
        LINKEDIN = "linkedin", "LinkedIn"

    website = models.ForeignKey(
        Website, on_delete=models.CASCADE, related_name="social_profiles"
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    handle = models.CharField(max_length=255)
    profile_url = models.URLField(blank=True)
    followers = models.PositiveIntegerField(default=0)
    engagement_rate = models.FloatField(default=0.0)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["website", "provider"], name="unique_social_per_website"
            )
        ]


class SocialEngagement(models.Model):
    profile = models.ForeignKey(
        SocialProfile, on_delete=models.CASCADE, related_name="engagements"
    )
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    likes = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    impressions = models.PositiveIntegerField(default=0)
    engagement_rate = models.FloatField(default=0.0)
    top_posts = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_start"]


class SocialMention(models.Model):
    class Sentiment(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEUTRAL = "neutral", "Neutral"
        NEGATIVE = "negative", "Negative"

    website = models.ForeignKey(
        Website, on_delete=models.CASCADE, related_name="social_mentions"
    )
    platform = models.CharField(max_length=50)
    author = models.CharField(max_length=255)
    content = models.TextField()
    url = models.URLField(max_length=1000, blank=True)
    sentiment = models.CharField(
        max_length=10, choices=Sentiment.choices, default=Sentiment.NEUTRAL
    )
    mentioned_at = models.DateTimeField()
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-mentioned_at"]
        indexes = [models.Index(fields=["website", "-mentioned_at"])]
