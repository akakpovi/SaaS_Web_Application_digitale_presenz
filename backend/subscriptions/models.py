import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Plan(models.Model):
    class Tier(models.TextChoices):
        FREE     = "free",     "Free"
        PRO      = "pro",      "Pro"
        BUSINESS = "business", "Business"

    tier         = models.CharField(max_length=10, choices=Tier.choices, unique=True)
    name         = models.CharField(max_length=50)
    description  = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_yearly  = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Limits
    max_websites        = models.IntegerField(default=1)
    max_scans_per_month = models.IntegerField(default=10)
    min_scan_interval   = models.CharField(max_length=4, default="24h")
    can_export_reports  = models.BooleanField(default=False)
    can_use_api         = models.BooleanField(default=False)
    can_add_team_members = models.BooleanField(default=False)
    max_team_members    = models.IntegerField(default=1)
    max_alert_channels  = models.IntegerField(default=1)

    features = models.JSONField(default=list, help_text="List of feature strings")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price_monthly"]
        verbose_name = "Plan"

    def __str__(self) -> str:
        return f"Plan({self.tier}, ${self.price_monthly}/mo)"


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE    = "active",    "Active"
        CANCELLED = "cancelled", "Cancelled"
        PAST_DUE  = "past_due",  "Past Due"
        TRIALING  = "trialing",  "Trialing"
        EXPIRED   = "expired",   "Expired"

    class BillingCycle(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY  = "yearly",  "Yearly"

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")

    status        = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    billing_cycle = models.CharField(max_length=8, choices=BillingCycle.choices, default=BillingCycle.MONTHLY)

    # Dates
    started_at    = models.DateTimeField(default=timezone.now)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end   = models.DateTimeField(null=True, blank=True)
    cancelled_at  = models.DateTimeField(null=True, blank=True)
    trial_end     = models.DateTimeField(null=True, blank=True)

    # Provider-independent billing fields
    external_id        = models.CharField(max_length=255, blank=True, help_text="Billing provider subscription ID")
    billing_provider   = models.CharField(max_length=50,  blank=True, help_text="e.g. stripe, paddle")
    billing_metadata   = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Subscription"

    def __str__(self) -> str:
        return f"Subscription({self.user.email}, {self.plan.tier}, {self.status})"

    @property
    def is_active(self) -> bool:
        return self.status in {self.Status.ACTIVE, self.Status.TRIALING}

    @property
    def is_free(self) -> bool:
        return self.plan.tier == Plan.Tier.FREE

    def cancel(self) -> None:
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.save(update_fields=["status", "cancelled_at", "updated_at"])
