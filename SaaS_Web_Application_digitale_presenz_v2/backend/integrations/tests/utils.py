from __future__ import annotations

import re
import uuid

from accounts.models import User
from integrations.models import OAuthConnection
from integrations.services.encryption import encrypt_connection_tokens
from organizations.models import Membership, Organization


def make_org(label: str = "Acme") -> Organization:
    suffix = uuid.uuid4().hex[:8]
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "org"
    user = User.objects.create_user(
        email=f"{slug}-{suffix}@example.com",
        password="test-password-123",
        full_name=f"{label} Owner",
    )
    organization = Organization.objects.create(
        name=f"{label} {suffix}",
        billing_owner=user,
    )
    Membership.objects.create(
        organization=organization,
        user=user,
        role=Membership.Role.OWNER,
    )
    return organization


def create_connection(
    organization: Organization,
    *,
    provider: str = OAuthConnection.Provider.LINKEDIN,
    external_account_id: str | None = None,
    access_token: str | None = None,
    refresh_token: str | None = None,
) -> OAuthConnection:
    external_account_id = external_account_id or f"acct-{uuid.uuid4().hex[:10]}"
    access_token = access_token or f"access-{uuid.uuid4().hex}"
    if refresh_token is None:
        refresh_token = f"refresh-{uuid.uuid4().hex}"

    encrypted = encrypt_connection_tokens(
        organization.id,
        provider,
        external_account_id,
        access_token,
        refresh_token,
    )
    return OAuthConnection.objects.create(
        organization=organization,
        provider=provider,
        external_account_id=external_account_id,
        access_token_ciphertext=encrypted.access_token_ciphertext,
        refresh_token_ciphertext=encrypted.refresh_token_ciphertext,
        key_version=encrypted.key_version,
    )
