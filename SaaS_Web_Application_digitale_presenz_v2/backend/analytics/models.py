from django.db import models
from django.conf import settings


class TrafficLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10, default="GET")
    ip_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    is_bot = models.BooleanField(default=False, db_index=True)
    language = models.CharField(max_length=10, null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    referrer = models.CharField(max_length=500, null=True, blank=True)
    status_code = models.IntegerField(default=200)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class AnalyticsEvent(models.Model):
    class EventType(models.TextChoices):
        PAGE_VIEW = "page_view", "Page View"
        SIGNUP = "signup", "Signup"
        LOGIN = "login", "Login"
        ADD_WEBSITE = "add_website", "Add Website"
        TRIGGER_SCAN = "trigger_scan", "Trigger Scan"
        PUBLIC_CHECK = "public_check", "Public Check"
        AD_CLICK = "ad_click", "Ad Click"
        COOKIE_ACCEPT = "cookie_accept", "Cookie Accept"
        COOKIE_ESSENTIAL = "cookie_essential", "Cookie Essential"
        PWA_INSTALL = "pwa_install", "PWA Install"
        PWA_DISMISS = "pwa_dismiss", "PWA Dismiss"
        AFFILIATE_CLICK = "affiliate_click", "Affiliate Click"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    event_type = models.CharField(
        max_length=50, choices=EventType.choices, db_index=True
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class AffiliateClick(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    partner = models.CharField(max_length=100)
    target_url = models.URLField()
    commission_eur = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    converted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
