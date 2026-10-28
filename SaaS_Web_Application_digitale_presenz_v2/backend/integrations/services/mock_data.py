"""Mock connector data for exercising rotation under a realistic row count.

The generated tokens are synthetic and live only in memory.  They are never
logged or written in plaintext; only their ciphertext reaches the database.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from accounts.models import User
from integrations.models import OAuthConnection, OrganizationDataKey
from organizations.models import Membership, Organization

from .encryption import encrypt_connection_tokens


@dataclass(frozen=True)
class MockConnection:
    connection_id: uuid.UUID
    organization_id: uuid.UUID
    provider: str
    external_account_id: str
    access_token: str
    refresh_token: str


def seed_mock_connector_data(
    organizations: int = 5,
    connections_per_org: int = 12,
    prefix: str = "loadtest",
) -> list[MockConnection]:
    """Create/update several organizations and dozens of encrypted connections.

    Returns the plaintext tokens only to the caller (tests or a local demo),
    never to a log.  Re-running with the same prefix is idempotent for
    organizations/accounts but refreshes the synthetic tokens and ciphertext.
    """

    if organizations < 1:
        raise ValueError("organizations must be at least 1.")
    if connections_per_org < 1:
        raise ValueError("connections_per_org must be at least 1.")
    if not prefix.strip():
        raise ValueError("prefix must not be empty.")

    providers = list(OAuthConnection.Provider.values)
    created: list[MockConnection] = []
    expires_at = timezone.now() + timedelta(hours=1)

    for org_index in range(organizations):
        email = f"mock-connector-{prefix}-{org_index}@example.invalid"
        user, user_created = User.objects.get_or_create(
            email=email,
            defaults={"full_name": f"Mock Connector {prefix} {org_index}"},
        )
        if user_created:
            user.set_unusable_password()
            user.save(update_fields=["password"])

        organization, _ = Organization.objects.get_or_create(
            name=f"Mock Connector {prefix} {org_index}",
            billing_owner=user,
            defaults={"is_personal": False},
        )
        Membership.objects.get_or_create(
            organization=organization,
            user=user,
            defaults={"role": Membership.Role.OWNER},
        )

        for connection_index in range(connections_per_org):
            provider = providers[connection_index % len(providers)]
            external_account_id = (
                f"mock-{prefix}-{org_index}-{connection_index}"
            )
            access_token = secrets.token_urlsafe(32)
            refresh_token = secrets.token_urlsafe(32)
            encrypted = encrypt_connection_tokens(
                organization.id,
                provider,
                external_account_id,
                access_token,
                refresh_token,
            )

            connection, _ = OAuthConnection.objects.get_or_create(
                organization=organization,
                provider=provider,
                external_account_id=external_account_id,
                defaults={
                    "access_token_ciphertext": encrypted.access_token_ciphertext,
                    "refresh_token_ciphertext": encrypted.refresh_token_ciphertext,
                    "key_version": encrypted.key_version,
                    "status": OAuthConnection.Status.ACTIVE,
                    "expires_at": expires_at,
                },
            )
            connection.access_token_ciphertext = encrypted.access_token_ciphertext
            connection.refresh_token_ciphertext = (
                encrypted.refresh_token_ciphertext
            )
            connection.key_version = encrypted.key_version
            connection.status = OAuthConnection.Status.ACTIVE
            connection.expires_at = expires_at
            connection.save(
                update_fields=[
                    "access_token_ciphertext",
                    "refresh_token_ciphertext",
                    "key_version",
                    "status",
                    "expires_at",
                    "updated_at",
                ]
            )

            created.append(
                MockConnection(
                    connection_id=connection.id,
                    organization_id=organization.id,
                    provider=provider,
                    external_account_id=external_account_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                )
            )

    return created


def count_mock_data(prefix: str = "loadtest") -> tuple[int, int]:
    """Return ``(organizations, connections)`` for a mock prefix."""

    organization_ids = Organization.objects.filter(
        name__startswith=f"Mock Connector {prefix} "
    ).values_list("id", flat=True)
    return (
        organization_ids.count(),
        OAuthConnection.objects.filter(
            organization_id__in=organization_ids
        ).count(),
    )


def mock_data_key_versions(prefix: str = "loadtest") -> list[int]:
    """Return the DEK versions used by a mock dataset (diagnostics only)."""

    organization_ids = Organization.objects.filter(
        name__startswith=f"Mock Connector {prefix} "
    ).values_list("id", flat=True)
    return list(
        OrganizationDataKey.objects.filter(
            organization_id__in=organization_ids,
            is_active=True,
        )
        .order_by("organization_id")
        .values_list("version", flat=True)
    )
