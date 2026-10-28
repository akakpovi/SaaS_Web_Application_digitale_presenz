"""OAuth authorization-code flow with PKCE and single-use state.

The state is bound to the authenticated user and organization.  Only its
SHA-256 digest is stored.  The PKCE verifier is encrypted with the same
envelope service as the connector tokens and its AAD includes the state hash,
so a verifier cannot be moved to another state or tenant.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from integrations.models import OAuthConnection, OAuthState, SocialAuditEvent
from integrations.providers import get_provider_client
from integrations.providers.base import (
    ProviderNotConfiguredError as ProviderClientNotConfigured,
    ProviderRequestError,
    UnsupportedProviderError as ProviderUnsupported,
)
from organizations.access import WRITE_ROLES, role_for_organization

from .audit import record_social_audit_event
from .encryption import (
    ConnectorCryptoError,
    ConnectorKeyConfigurationError,
    decrypt_for_organization,
    decrypt_token,
    encrypt_connection_tokens,
    encrypt_for_organization,
    state_aad,
)

logger = logging.getLogger("integrations.oauth")

STATE_BYTES = 48
VERIFIER_BYTES = 64
MAX_AUTHORIZATION_CODE_LENGTH = 2048
MAX_STATE_LENGTH = 128


class OAuthFlowError(Exception):
    """A safe, client-facing OAuth failure."""

    status_code = 400
    code = "oauth_error"
    default_message = "OAuth flow failed."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class OAuthForbidden(OAuthFlowError):
    status_code = 403
    code = "forbidden"
    default_message = "Your organization role does not allow connecting social accounts."


class UnsupportedOAuthProvider(OAuthFlowError):
    status_code = 400
    code = "unsupported_provider"
    default_message = "Unsupported OAuth provider."


class OAuthProviderNotConfigured(OAuthFlowError):
    status_code = 503
    code = "provider_not_configured"
    default_message = "The OAuth provider is not configured."


class InvalidOAuthRequest(OAuthFlowError):
    status_code = 400
    code = "invalid_request"
    default_message = "The OAuth callback request is incomplete."


class InvalidOAuthState(OAuthFlowError):
    status_code = 400
    code = "invalid_state"
    default_message = "The OAuth state is invalid or expired."


class OAuthExchangeFailed(OAuthFlowError):
    status_code = 502
    code = "oauth_exchange_failed"
    default_message = "The provider could not exchange the authorization code."


class OAuthIdentityFailed(OAuthFlowError):
    status_code = 502
    code = "oauth_identity_failed"
    default_message = "The provider could not identify the connected account."


class OAuthStorageFailed(OAuthFlowError):
    status_code = 500
    code = "oauth_storage_failed"
    default_message = "The connected account could not be stored."


@dataclass(frozen=True)
class AuthorizationRequest:
    authorization_url: str
    provider: str
    expires_at: datetime


def _normalize_provider(provider: str) -> str:
    return (provider or "").strip().lower()


def _client(provider: str):
    try:
        return get_provider_client(provider)
    except ProviderUnsupported:
        raise UnsupportedOAuthProvider() from None


def _code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _state_ttl() -> int:
    try:
        ttl = int(getattr(settings, "OAUTH_STATE_TTL_SECONDS", 600))
    except (TypeError, ValueError):
        raise OAuthProviderNotConfigured(
            "The OAuth state lifetime is invalid."
        ) from None
    if ttl < 60 or ttl > 1800:
        raise OAuthProviderNotConfigured(
            "The OAuth state lifetime must be between 60 and 1800 seconds."
        )
    return ttl


def start_oauth_flow(organization, user, provider: str) -> AuthorizationRequest:
    """Create a state row and return the provider authorization URL."""

    provider = _normalize_provider(provider)
    if role_for_organization(user, organization) not in WRITE_ROLES:
        raise OAuthForbidden()

    client = _client(provider)
    raw_state = secrets.token_urlsafe(STATE_BYTES)
    state_hash = hashlib.sha256(raw_state.encode("utf-8")).hexdigest()
    code_verifier = secrets.token_urlsafe(VERIFIER_BYTES)
    challenge = _code_challenge(code_verifier)
    ttl = _state_ttl()
    expires_at = timezone.now() + timedelta(seconds=ttl)

    redirect_uri = str(getattr(client, "redirect_uri", "") or "").strip()
    if not redirect_uri:
        raise OAuthProviderNotConfigured()

    try:
        verifier_ciphertext, verifier_key_version = encrypt_for_organization(
            organization.id,
            code_verifier,
            state_aad(organization.id, provider, state_hash),
        )
    except ConnectorKeyConfigurationError:
        raise OAuthProviderNotConfigured() from None
    except ConnectorCryptoError:
        raise OAuthStorageFailed() from None

    try:
        authorization_url = client.authorization_url(
            state=raw_state,
            code_challenge=challenge,
        )
    except ProviderClientNotConfigured:
        raise OAuthProviderNotConfigured() from None

    try:
        OAuthState.objects.create(
            state_hash=state_hash,
            organization=organization,
            user=user,
            provider=provider,
            redirect_uri=redirect_uri,
            code_verifier_ciphertext=verifier_ciphertext,
            code_verifier_key_version=verifier_key_version,
            expires_at=expires_at,
        )
    except DatabaseError:
        raise OAuthStorageFailed() from None
    logger.info(
        "oauth_authorize_created org=%s provider=%s",
        organization.id,
        provider,
    )
    return AuthorizationRequest(
        authorization_url=authorization_url,
        provider=provider,
        expires_at=expires_at,
    )


def _consume_state(provider: str, raw_state: str) -> OAuthState:
    """Consume a state and return the user/organization it was issued for.

    The callback is a top-level browser redirect from the provider and cannot
    carry the application's JWT header.  The unguessable state row is therefore
    the authority: it names the initiating user and tenant.  The request user is
    deliberately not consulted, so a stale or unrelated session cannot redirect
    the connection to another tenant.
    """

    if (
        not raw_state
        or len(raw_state) > MAX_STATE_LENGTH
        or len(raw_state) < 20
    ):
        raise InvalidOAuthState()

    state_hash = hashlib.sha256(raw_state.encode("utf-8")).hexdigest()
    now = timezone.now()

    with transaction.atomic():
        state = (
            OAuthState.objects.select_for_update()
            .select_related("organization", "user")
            .filter(state_hash=state_hash)
            .first()
        )
        if state is None:
            raise InvalidOAuthState()
        if state.consumed_at is not None:
            raise InvalidOAuthState()
        if state.expires_at <= now:
            raise InvalidOAuthState()
        if state.provider != provider:
            raise InvalidOAuthState()
        if not state.user.is_active:
            raise InvalidOAuthState()
        if role_for_organization(state.user, state.organization) not in WRITE_ROLES:
            raise InvalidOAuthState()

        state.consumed_at = now
        state.save(update_fields=["consumed_at"])

    return state


def _decrypt_verifier(state: OAuthState) -> str:
    try:
        return decrypt_for_organization(
            state.organization_id,
            state.code_verifier_ciphertext,
            state.code_verifier_key_version,
            state_aad(
                state.organization_id,
                state.provider,
                state.state_hash,
            ),
        )
    except ConnectorCryptoError:
        raise InvalidOAuthState() from None


def _preserved_refresh_token(existing, tokens) -> str:
    if tokens.refresh_token:
        return tokens.refresh_token
    if existing is None or not existing.refresh_token_ciphertext:
        return ""
    try:
        return decrypt_token(existing, "refresh_token")
    except ConnectorCryptoError:
        # A corrupt old refresh token must not block a fresh access token.
        return ""


def complete_oauth_flow(
    provider: str,
    code: str | None,
    raw_state: str | None,
    *,
    request=None,
) -> OAuthConnection:
    """Validate/consume the state, exchange the code, and upsert the account."""

    provider = _normalize_provider(provider)
    client = _client(provider)
    if (
        not code
        or len(code) > MAX_AUTHORIZATION_CODE_LENGTH
        or not raw_state
    ):
        raise InvalidOAuthRequest()

    state = _consume_state(provider, raw_state)
    verifier = _decrypt_verifier(state)

    redirect_uri = state.redirect_uri or str(
        getattr(client, "redirect_uri", "") or ""
    ).strip()
    if not redirect_uri:
        raise OAuthProviderNotConfigured()

    try:
        tokens = client.exchange_code(
            code=code,
            code_verifier=verifier,
            redirect_uri=redirect_uri,
        )
    except ProviderClientNotConfigured:
        raise OAuthProviderNotConfigured() from None
    except ProviderRequestError:
        raise OAuthExchangeFailed() from None

    try:
        identity = client.fetch_identity(access_token=tokens.access_token)
    except ProviderClientNotConfigured:
        raise OAuthProviderNotConfigured() from None
    except ProviderRequestError:
        raise OAuthIdentityFailed() from None

    if not identity.subject or len(identity.subject) > 255:
        raise OAuthIdentityFailed()

    existing = OAuthConnection.objects.filter(
        organization_id=state.organization_id,
        provider=provider,
        external_account_id=identity.subject,
    ).first()
    refresh_token = _preserved_refresh_token(existing, tokens)
    try:
        encrypted = encrypt_connection_tokens(
            state.organization_id,
            provider,
            identity.subject,
            tokens.access_token,
            refresh_token,
        )
    except ConnectorKeyConfigurationError:
        raise OAuthProviderNotConfigured() from None
    except ConnectorCryptoError:
        raise OAuthStorageFailed() from None

    expires_at = None
    if tokens.expires_in and tokens.expires_in > 0:
        expires_at = timezone.now() + timedelta(seconds=tokens.expires_in)

    try:
        with transaction.atomic():
            connection, _created = OAuthConnection.objects.update_or_create(
                organization_id=state.organization_id,
                provider=provider,
                external_account_id=identity.subject,
                defaults={
                    "access_token_ciphertext": encrypted.access_token_ciphertext,
                    "refresh_token_ciphertext": encrypted.refresh_token_ciphertext,
                    "key_version": encrypted.key_version,
                    "refresh_failures": 0,
                    "status": OAuthConnection.Status.ACTIVE,
                    "expires_at": expires_at,
                },
            )
            # The connection and its audit row commit together.  If the audit
            # insert fails, the upsert is rolled back rather than producing an
            # unaudited credential.
            record_social_audit_event(
                organization_id=state.organization_id,
                actor=state.user,
                action=SocialAuditEvent.Action.CONNECTED,
                provider=provider,
                external_account_id=identity.subject,
                connection_id=connection.id,
                request=request,
            )
    except (DatabaseError, IntegrityError):
        raise OAuthStorageFailed() from None

    logger.info(
        "oauth_connection_upserted org=%s provider=%s",
        state.organization_id,
        provider,
    )
    return connection
