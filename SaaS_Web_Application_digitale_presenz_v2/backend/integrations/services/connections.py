"""Lifecycle operations for stored social connections.

Disconnecting is deliberately fail-closed: the provider is asked to revoke the
access token before the local row is deleted.  If the provider cannot be
reached, the connection is kept so the caller can retry instead of silently
leaving a usable token behind at LinkedIn.
"""

from __future__ import annotations

import logging

from django.db import DatabaseError, transaction

from integrations.models import SocialAuditEvent
from integrations.providers import get_provider_client
from integrations.providers.base import (
    ProviderNotConfiguredError,
    ProviderRequestError,
    UnsupportedProviderError,
)

from .audit import record_social_audit_event
from .encryption import ConnectorCryptoError, decrypt_token
from .oauth import OAuthFlowError

logger = logging.getLogger("integrations.connections")


class OAuthRevocationFailed(OAuthFlowError):
    status_code = 502
    code = "oauth_revocation_failed"
    default_message = "The provider could not revoke the connection."


class OAuthDeleteFailed(OAuthFlowError):
    status_code = 500
    code = "oauth_delete_failed"
    default_message = "The connection could not be deleted."


def disconnect_connection(connection, *, actor=None, request=None) -> None:
    """Revoke the provider token, then delete the local connection.

    A ciphertext that can no longer be opened cannot be revoked (the plaintext
    is unavailable); the row is still removed so a corrupt credential does not
    become impossible to clean up.  A provider network or configuration error
    keeps the row intact and returns a safe 502 to the caller.

    The successful deletion and its audit event are committed atomically, so a
    failed audit insert cannot leave an unaudited disconnection.
    """

    access_token = ""
    try:
        access_token = decrypt_token(connection, "access_token")
    except ConnectorCryptoError:
        logger.warning(
            "oauth_disconnect_token_unavailable org=%s provider=%s",
            connection.organization_id,
            connection.provider,
        )

    if access_token:
        try:
            client = get_provider_client(connection.provider)
        except UnsupportedProviderError:
            logger.warning(
                "oauth_disconnect_provider_unsupported org=%s provider=%s",
                connection.organization_id,
                connection.provider,
            )
        else:
            revoke = getattr(client, "revoke_token", None)
            if callable(revoke):
                try:
                    revoke(access_token=access_token)
                except ProviderNotConfiguredError:
                    raise OAuthRevocationFailed(
                        "The provider is not configured; the connection was kept."
                    ) from None
                except ProviderRequestError:
                    raise OAuthRevocationFailed() from None

    # ``delete()`` clears the instance's primary key; snapshot every audit
    # field that must survive the row removal.
    audit_snapshot = {
        "organization_id": connection.organization_id,
        "provider": connection.provider,
        "external_account_id": connection.external_account_id,
        "connection_id": connection.id,
    }
    try:
        with transaction.atomic():
            connection.delete()
            record_social_audit_event(
                **audit_snapshot,
                actor=actor,
                action=SocialAuditEvent.Action.DISCONNECTED,
                request=request,
            )
    except DatabaseError:
        raise OAuthDeleteFailed() from None

    logger.info(
        "oauth_connection_deleted org=%s provider=%s",
        connection.organization_id,
        connection.provider,
    )
