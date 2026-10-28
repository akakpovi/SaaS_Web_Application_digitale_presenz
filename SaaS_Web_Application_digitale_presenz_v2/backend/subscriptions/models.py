import hashlib
import secrets
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
        AGENCY   = "agency",   "Agency"

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

    # Provider price identifiers (Paddle/Stripe).  Stored per plan so the
    # checkout can map a tier + billing cycle to the exact price the provider
    # will charge, without hard-coding anything in the frontend.
    external_price_id_monthly = models.CharField(
        max_length=255, blank=True, default="",
        help_text="Provider price ID for the monthly cycle (e.g. pri_...)",
    )
    external_price_id_yearly = models.CharField(
        max_length=255, blank=True, default="",
        help_text="Provider price ID for the yearly cycle (e.g. pri_...)",
    )
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

    def price_id_for(self, billing_cycle: str) -> str:
        """Return the provider price ID matching *billing_cycle*."""
        if billing_cycle == self.BillingCycle.YEARLY:
            return self.plan.external_price_id_yearly
        return self.plan.external_price_id_monthly


class BillingEvent(models.Model):
    """Journal idempotent des webhooks de paiement.

    ``(provider, event_id)`` est unique : un événement rejoué par le
    prestataire (ce qui arrive systématiquement après un timeout) ne peut pas
    appliquer deux fois le même changement d'abonnement.  Le payload brut est
    conservé pour l'audit et le rejeu manuel.
    """

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=50)
    event_id = models.CharField(max_length=255)
    event_type = models.CharField(max_length=100, blank=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RECEIVED)
    error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "event_id"],
                name="unique_billing_event_per_provider",
            )
        ]
        indexes = [
            models.Index(
                fields=["provider", "event_type"],
                name="billing_event_provider_idx",
            )
        ]
        verbose_name = "Billing Event"

    def __str__(self) -> str:
        return f"BillingEvent({self.provider}, {self.event_type}, {self.status})"


class ApiKey(models.Model):
    """Clé d'accès programmatique, réservée aux offres ``can_use_api``.

    Seul le hash SHA-256 est stocké : la clé en clair n'est affichée qu'une
    fois, à la création.  Le préfixe permet de retrouver la clé sans exposer
    le secret, et la révocation est immédiate.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="api_keys"
    )
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=16, unique=True)
    hashed_key = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "API Key"

    def __str__(self) -> str:
        return f"ApiKey({self.user_id}, {self.name}, {self.prefix})"

    @staticmethod
    def hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @classmethod
    def issue(cls, user, name: str) -> tuple["ApiKey", str]:
        prefix = secrets.token_hex(4)
        secret = secrets.token_urlsafe(32)
        raw_key = f"pk_{prefix}_{secret}"
        key = cls.objects.create(
            user=user,
            name=name[:100],
            prefix=prefix,
            hashed_key=cls.hash_key(raw_key),
        )
        return key, raw_key

    def matches(self, raw_key: str) -> bool:
        return secrets.compare_digest(self.hashed_key, self.hash_key(raw_key))

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None
