"""Tenant-scoped models for social OAuth connectors.

Only ciphertext is persisted.  The plaintext tokens never touch a model field,
a serializer, ``__str__`` or a log line.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from organizations.models import Organization


class OAuthConnection(models.Model):
    """A social account connected by one organization.

    ``key_version`` points at the organization DEK version used for the two
    ciphertext fields.  It is deliberately kept next to the ciphertext so a
    rotation can migrate old rows without guessing which key to use.
    """

    class Provider(models.TextChoices):
        GOOGLE = "google", "Google"
        LINKEDIN = "linkedin", "LinkedIn"
        FACEBOOK = "facebook", "Facebook"
        INSTAGRAM = "instagram", "Instagram"
        TWITTER = "twitter", "Twitter / X"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="oauth_connections",
    )
    provider = models.CharField(max_length=32, choices=Provider.choices)
    external_account_id = models.CharField(max_length=255)
    access_token_ciphertext = models.TextField()
    refresh_token_ciphertext = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    key_version = models.PositiveIntegerField(default=1)
    refresh_failures = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization", "provider", "external_account_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "provider", "external_account_id"],
                name="uniq_oauth_conn_account",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "provider", "status"],
                name="oauth_conn_org_prov_status_idx",
            ),
            models.Index(
                fields=["status", "expires_at"],
                name="oauth_conn_status_expires_idx",
            ),
        ]
        verbose_name = "OAuth connection"

    def __str__(self) -> str:
        # Never include token material, not even ciphertext.
        return f"{self.provider}:{self.external_account_id}@{self.organization_id}"


class OAuthState(models.Model):
    """A short-lived, single-use OAuth ``state`` record.

    Only the SHA-256 digest of the browser-visible state is stored.  A database
    leak cannot be replayed against the callback endpoint.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state_hash = models.CharField(max_length=64, unique=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="oauth_states",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="oauth_states",
    )
    provider = models.CharField(max_length=32, choices=OAuthConnection.Provider.choices)
    redirect_uri = models.URLField(max_length=500, blank=True, default="")
    code_verifier_ciphertext = models.TextField(blank=True, default="")
    code_verifier_key_version = models.PositiveIntegerField(default=1)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["organization", "provider"],
                name="oauth_state_org_provider_idx",
            ),
            models.Index(fields=["expires_at"], name="oauth_state_expires_idx"),
        ]
        verbose_name = "OAuth state"

    def __str__(self) -> str:
        return f"{self.provider}@{self.organization_id} (expires {self.expires_at:%Y-%m-%d %H:%M:%S})"


class SocialAuditEventQuerySet(models.QuerySet):
    """Append-only queryset for the social connector audit trail."""

    def update(self, *args, **kwargs):
        raise ValidationError("Social audit events are immutable.")

    def delete(self, *args, **kwargs):
        raise ValidationError("Social audit events are immutable.")


class SocialAuditEvent(models.Model):
    """An append-only record of a social connector lifecycle action.

    The organization is the tenant boundary.  ``actor`` is nullable so the
    event survives user deletion, while ``actor_email`` preserves the identity
    at the time of the action.  ``connection_id`` is a snapshot rather than a
    foreign key: the event must remain readable after the connection row is
    removed.

    Immutability is enforced at the model/queryset layer.  Operational access
    should use a read-only database role in production; the model guard keeps
    accidental application writes from silently rewriting history.
    """

    class Action(models.TextChoices):
        CONNECTED = "connected", "Connected"
        DISCONNECTED = "disconnected", "Disconnected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="social_audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="social_audit_events",
    )
    actor_email = models.EmailField(blank=True, default="")
    action = models.CharField(max_length=32, choices=Action.choices, db_index=True)
    provider = models.CharField(max_length=32, choices=OAuthConnection.Provider.choices)
    external_account_id = models.CharField(max_length=255)
    connection_id = models.UUIDField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(
        protocol="both",
        unpack_ipv4=False,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = SocialAuditEventQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["organization", "created_at"],
                name="social_audit_org_created_idx",
            ),
            models.Index(
                fields=["organization", "action"],
                name="social_audit_org_action_idx",
            ),
        ]
        verbose_name = "Social audit event"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Social audit events are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Social audit events are immutable.")

    def __str__(self) -> str:
        return (
            f"{self.action}:{self.provider}:{self.external_account_id}"
            f"@{self.organization_id}"
        )


class OrganizationDataKey(models.Model):
    """A per-organization data encryption key (DEK), wrapped by the KEK.

    Multiple versions are retained so a rotation can decrypt rows written
    under an older key.  Exactly one row per organization is active; the
    partial unique constraint enforces that invariant in PostgreSQL.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="connector_data_keys",
    )
    version = models.PositiveIntegerField()
    wrapped_dek = models.TextField()
    kek_version = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rotated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["organization", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "version"],
                name="uniq_conn_dek_org_version",
            ),
            models.UniqueConstraint(
                fields=["organization"],
                condition=models.Q(is_active=True),
                name="unique_active_dek_per_org",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "is_active"],
                name="conn_dek_org_active_idx",
            ),
        ]
        verbose_name = "Organization connector data key"

    def __str__(self) -> str:
        return f"{self.organization_id}:v{self.version}"
