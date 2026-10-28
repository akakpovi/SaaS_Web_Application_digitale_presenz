import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


def invitation_default_expiry():
    return timezone.now() + timedelta(days=7)


class Organization(models.Model):
    """A tenant boundary for websites and their team members.

    Personal organizations are created lazily for website owners.  The
    ``is_personal`` flag and its partial unique constraint make that creation
    safe under concurrent requests without preventing a billing owner from
    owning additional shared organizations later.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    billing_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_organizations",
    )
    is_personal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["billing_owner"],
                condition=Q(is_personal=True, billing_owner__isnull=False),
                name="unique_personal_organization_per_billing_owner",
            ),
        ]
        indexes = [
            models.Index(fields=["billing_owner", "is_personal"]),
        ]
        verbose_name = "Organization"

    def __str__(self) -> str:
        return self.name


class Membership(models.Model):
    """A user's role inside one organization."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        ANALYST = "analyst", "Analyst"
        VIEWER = "viewer", "Viewer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(max_length=12, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization", "user"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="unique_organization_membership",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "organization"]),
        ]
        verbose_name = "Organization membership"

    def __str__(self) -> str:
        return f"{self.user_id}@{self.organization_id}:{self.role}"


class OrganizationInvitation(models.Model):
    """A pending invitation for an e-mail that may not have an account yet.

    Only a SHA-256 digest of the acceptance token is stored.  Invitations are
    single-use and expire after seven days; accepting one creates the
    membership and records the acceptance for the organization audit trail.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    ASSIGNABLE_ROLE_CHOICES = [
        (Membership.Role.ADMIN, "Admin"),
        (Membership.Role.ANALYST, "Analyst"),
        (Membership.Role.VIEWER, "Viewer"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField(db_index=True)
    role = models.CharField(max_length=12, choices=ASSIGNABLE_ROLE_CHOICES)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_organization_invitations",
    )
    expires_at = models.DateTimeField(default=invitation_default_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"],
                condition=Q(status="pending"),
                name="unique_pending_invitation_per_organization_email",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["email", "status"]),
        ]
        verbose_name = "Organization invitation"

    @property
    def is_expired(self) -> bool:
        return self.status == self.Status.PENDING and self.expires_at <= timezone.now()

    def __str__(self) -> str:
        return f"{self.email}@{self.organization_id}:{self.role} ({self.status})"
