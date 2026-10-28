"""Refresh expiring social connector access tokens.

The refresh token is decrypted only in memory, exchanged with the provider and
the resulting pair is re-encrypted with the organization's current DEK before
any database write.  No token is logged or returned by the task.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from integrations.models import OAuthConnection
from integrations.providers import get_provider_client
from integrations.providers.base import (
    ProviderNotConfiguredError,
    ProviderRequestError,
    UnsupportedProviderError,
)

from .encryption import (
    ConnectorCryptoError,
    ConnectorKeyConfigurationError,
    decrypt_token,
    encrypt_connection_tokens,
)

logger = logging.getLogger("integrations.refresh")

REFRESH_WINDOW_HOURS = 72
REFRESH_BATCH_SIZE = 200
REFRESH_MAX_FAILURES = 3


def _max_refresh_failures() -> int:
    try:
        value = int(getattr(settings, "SOCIAL_TOKEN_REFRESH_MAX_FAILURES", REFRESH_MAX_FAILURES))
    except (TypeError, ValueError):
        return REFRESH_MAX_FAILURES
    return max(1, min(value, 100))


def _mark_status(connection: OAuthConnection, status: str) -> None:
    if connection.status == status:
        return
    connection.status = status
    connection.save(update_fields=["status", "updated_at"])


def refresh_connection(connection: OAuthConnection, *, client=None) -> str:
    """Refresh one LinkedIn connection and persist the rotated token pair.

    Returns a small outcome code used by the Celery task for observability.
    The function never returns, logs or raises token material.
    """

    if connection.provider != OAuthConnection.Provider.LINKEDIN:
        return "unsupported_provider"

    if not connection.refresh_token_ciphertext:
        # Without a refresh token there is no recovery path.  Keep an expired
        # connection visibly expired instead of retrying it forever.
        if connection.expires_at and connection.expires_at <= timezone.now():
            _mark_status(connection, OAuthConnection.Status.EXPIRED)
        logger.info(
            "oauth_refresh_missing_refresh_token org=%s provider=%s",
            connection.organization_id,
            connection.provider,
        )
        return "missing_refresh_token"

    try:
        refresh_token = decrypt_token(connection, "refresh_token")
    except ConnectorCryptoError:
        _mark_status(connection, OAuthConnection.Status.ERROR)
        logger.warning(
            "oauth_refresh_decryption_failed org=%s provider=%s",
            connection.organization_id,
            connection.provider,
        )
        return "decryption_failed"

    if client is None:
        try:
            client = get_provider_client(connection.provider)
        except UnsupportedProviderError:
            logger.warning(
                "oauth_refresh_provider_unsupported org=%s provider=%s",
                connection.organization_id,
                connection.provider,
            )
            return "unsupported_provider"

    try:
        tokens = client.refresh_access_token(refresh_token=refresh_token)
    except ProviderNotConfiguredError:
        # A missing deployment secret affects every connection.  Leave the row
        # eligible so the next scheduled run succeeds after configuration.
        logger.warning(
            "oauth_refresh_provider_not_configured org=%s provider=%s",
            connection.organization_id,
            connection.provider,
        )
        return "provider_not_configured"
    except ProviderRequestError:
        # Count consecutive provider failures.  A single network blip must not
        # destroy the connection, but repeated failures are parked in ERROR so
        # Beat stops selecting it and the UI shows that a reconnect is needed.
        threshold = _max_refresh_failures()
        failures = min(connection.refresh_failures + 1, 1_000_000)
        connection.refresh_failures = failures
        update_fields = ["refresh_failures", "updated_at"]
        if failures >= threshold and connection.status != OAuthConnection.Status.ERROR:
            connection.status = OAuthConnection.Status.ERROR
            update_fields.append("status")
        connection.save(update_fields=update_fields)
        logger.warning(
            "oauth_refresh_provider_error org=%s provider=%s failures=%s threshold=%s",
            connection.organization_id,
            connection.provider,
            failures,
            threshold,
        )
        return "provider_error"

    if not tokens.access_token:
        logger.warning(
            "oauth_refresh_empty_access_token org=%s provider=%s",
            connection.organization_id,
            connection.provider,
        )
        return "empty_access_token"

    # LinkedIn may rotate the refresh token.  When it omits one, retain the
    # existing refresh token rather than storing an empty value.
    new_refresh_token = tokens.refresh_token or refresh_token

    try:
        encrypted = encrypt_connection_tokens(
            connection.organization_id,
            connection.provider,
            connection.external_account_id,
            tokens.access_token,
            new_refresh_token,
        )
    except ConnectorKeyConfigurationError:
        logger.warning(
            "oauth_refresh_key_configuration_error org=%s provider=%s",
            connection.organization_id,
            connection.provider,
        )
        return "encryption_failed"
    except ConnectorCryptoError:
        logger.warning(
            "oauth_refresh_encryption_failed org=%s provider=%s",
            connection.organization_id,
            connection.provider,
        )
        return "encryption_failed"

    expires_at = None
    if tokens.expires_in and tokens.expires_in > 0:
        expires_at = timezone.now() + timedelta(seconds=tokens.expires_in)

    connection.access_token_ciphertext = encrypted.access_token_ciphertext
    connection.refresh_token_ciphertext = encrypted.refresh_token_ciphertext
    connection.key_version = encrypted.key_version
    connection.expires_at = expires_at
    connection.refresh_failures = 0
    connection.status = OAuthConnection.Status.ACTIVE
    connection.save(
        update_fields=[
            "access_token_ciphertext",
            "refresh_token_ciphertext",
            "key_version",
            "expires_at",
            "refresh_failures",
            "status",
            "updated_at",
        ]
    )

    logger.info(
        "oauth_connection_refreshed org=%s provider=%s",
        connection.organization_id,
        connection.provider,
    )
    return "refreshed"
