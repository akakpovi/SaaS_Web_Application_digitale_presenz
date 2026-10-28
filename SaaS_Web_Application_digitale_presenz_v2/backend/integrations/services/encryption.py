"""AES-256-GCM envelope encryption for social connector tokens.

Design
------
* The KEK comes from the environment (``CONNECTOR_KEK_V<N>``) and never from
  the database.
* Every organization owns one active DEK.  The DEK is generated randomly and
  stored only wrapped (encrypted) by the active KEK.
* Each token is encrypted with the organization DEK.  The AAD binds the
  ciphertext to the organization, provider, external account and token field;
  copying a ciphertext into another tenant's row therefore fails closed.
* Logs only carry non-secret metadata (organization id, provider, field and
  key version).  Errors are deliberately generic.

The on-disk envelope is ``v1.<nonce-b64>.<ciphertext+tag-b64>``.  The GCM tag
is appended by ``cryptography`` and authenticated on decrypt.
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import quote

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction

logger = logging.getLogger("integrations.crypto")

ENVELOPE_VERSION = "v1"
KEY_BYTES = 32
NONCE_BYTES = 12
TOKEN_FIELDS = frozenset({"access_token", "refresh_token"})


class ConnectorCryptoError(Exception):
    """Base class for connector vault failures."""


class ConnectorKeyConfigurationError(ImproperlyConfigured, ConnectorCryptoError):
    """The KEK key ring is missing or invalid; the app must not start."""


class ConnectorDecryptionError(ConnectorCryptoError):
    """A ciphertext could not be authenticated or decoded."""


@dataclass(frozen=True)
class KeyRing:
    """All configured KEK versions, plus the one used for new DEKs."""

    keys: Mapping[int, bytes]
    active_version: int

    def kek(self, version: int | None = None) -> bytes:
        selected = self.active_version if version is None else int(version)
        try:
            return self.keys[selected]
        except KeyError:
            raise ConnectorKeyConfigurationError(
                f"CONNECTOR_KEK_V{selected} is not configured"
            ) from None


@dataclass(frozen=True)
class EncryptedTokens:
    access_token_ciphertext: str
    refresh_token_ciphertext: str
    key_version: int


def _b64encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


def get_keyring() -> KeyRing:
    """Load and validate the KEK key ring from Django settings.

    Settings are read on every call (rather than cached) so tests and
    management commands can exercise rotation and missing-key scenarios.
    """

    raw = getattr(settings, "CONNECTOR_KEKS", None) or {}
    if not raw:
        raise ConnectorKeyConfigurationError(
            "No connector KEK is configured; set CONNECTOR_KEK_V1."
        )

    keys: dict[int, bytes] = {}
    for version, encoded in raw.items():
        try:
            version_int = int(version)
        except (TypeError, ValueError):
            raise ConnectorKeyConfigurationError(
                "A connector KEK has an invalid version number."
            ) from None

        try:
            key = base64.b64decode(str(encoded), validate=True)
        except (binascii.Error, TypeError, ValueError):
            raise ConnectorKeyConfigurationError(
                f"CONNECTOR_KEK_V{version_int} is not valid base64."
            ) from None

        if len(key) != KEY_BYTES:
            raise ConnectorKeyConfigurationError(
                f"CONNECTOR_KEK_V{version_int} must decode to exactly "
                f"{KEY_BYTES} bytes (got {len(key)})."
            )
        keys[version_int] = key

    active_version = int(getattr(settings, "CONNECTOR_KEK_ACTIVE_VERSION", 0) or 0)
    if active_version not in keys:
        raise ConnectorKeyConfigurationError(
            "CONNECTOR_KEK_ACTIVE_VERSION does not reference a configured KEK."
        )

    return KeyRing(keys=keys, active_version=active_version)


def _seal_bytes(plaintext: bytes, key: bytes, aad: bytes) -> str:
    if len(key) != KEY_BYTES:
        raise ConnectorCryptoError("Connector encryption key has an invalid length.")
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
    return f"{ENVELOPE_VERSION}.{_b64encode(nonce)}.{_b64encode(ciphertext)}"


def _open_bytes(envelope: str, key: bytes, aad: bytes) -> bytes:
    try:
        version, nonce_b64, ciphertext_b64 = str(envelope).split(".")
        if version != ENVELOPE_VERSION:
            raise ValueError("unsupported envelope version")
        nonce = _b64decode(nonce_b64)
        ciphertext = _b64decode(ciphertext_b64)
        if len(nonce) != NONCE_BYTES or not ciphertext:
            raise ValueError("invalid envelope")
        return AESGCM(key).decrypt(nonce, ciphertext, aad)
    except (InvalidTag, UnicodeDecodeError, ValueError, TypeError, binascii.Error):
        # Never include the envelope, plaintext or key in the exception.
        raise ConnectorDecryptionError(
            "Unable to decrypt connector secret."
        ) from None


def seal_secret(plaintext: str, key: bytes, aad: bytes) -> str:
    """Encrypt a UTF-8 secret with a 32-byte key and the supplied AAD."""

    if not isinstance(plaintext, str):
        raise TypeError("Connector secrets must be strings.")
    return _seal_bytes(plaintext.encode("utf-8"), key, aad)


def open_secret(envelope: str, key: bytes, aad: bytes) -> str:
    """Decrypt an envelope, failing closed on any authentication error."""

    try:
        return _open_bytes(envelope, key, aad).decode("utf-8")
    except UnicodeDecodeError:
        raise ConnectorDecryptionError(
            "Unable to decrypt connector secret."
        ) from None


def _aad_component(value: object) -> str:
    return quote(str(value), safe="")


def token_aad(
    organization_id: object,
    provider: str,
    external_account_id: str,
    field: str,
) -> bytes:
    """Bind a token ciphertext to tenant, provider, account and field."""

    if field not in TOKEN_FIELDS:
        raise ValueError(f"Unsupported token field: {field}")
    return (
        f"org={_aad_component(organization_id)}"
        f"|provider={_aad_component(provider)}"
        f"|account={_aad_component(external_account_id)}"
        f"|field={field}"
    ).encode("utf-8")


def state_aad(
    organization_id: object,
    provider: str,
    state_hash: str,
    field: str = "code_verifier",
) -> bytes:
    """Bind the encrypted PKCE verifier to its exact OAuth state."""

    return (
        f"org={_aad_component(organization_id)}"
        f"|provider={_aad_component(provider)}"
        f"|state={_aad_component(state_hash)}"
        f"|field={_aad_component(field)}"
    ).encode("utf-8")


def data_key_aad(organization_id: object, version: int, kek_version: int) -> bytes:
    """Bind a wrapped DEK to its organization, DEK version and KEK version."""

    return (
        f"org={_aad_component(organization_id)}"
        f"|dek={int(version)}"
        f"|kek={int(kek_version)}"
    ).encode("utf-8")


def wrap_data_key(
    dek: bytes,
    organization_id: object,
    version: int,
    kek_version: int,
    kek: bytes,
) -> str:
    if len(dek) != KEY_BYTES:
        raise ConnectorCryptoError("Data encryption key has an invalid length.")
    return _seal_bytes(
        dek,
        kek,
        data_key_aad(organization_id, version, kek_version),
    )


def unwrap_data_key(data_key, keyring: KeyRing | None = None) -> bytes:
    keyring = keyring or get_keyring()
    try:
        kek = keyring.kek(data_key.kek_version)
        dek = _open_bytes(
            data_key.wrapped_dek,
            kek,
            data_key_aad(
                data_key.organization_id,
                data_key.version,
                data_key.kek_version,
            ),
        )
    except ConnectorDecryptionError:
        raise
    if len(dek) != KEY_BYTES:
        raise ConnectorDecryptionError("Unable to decrypt connector secret.")
    return dek


def _get_or_create_active_data_key(organization_id):
    from integrations.models import OrganizationDataKey
    from organizations.models import Organization

    existing = OrganizationDataKey.objects.filter(
        organization_id=organization_id,
        is_active=True,
    ).first()
    if existing is not None:
        return existing

    keyring = get_keyring()
    try:
        with transaction.atomic():
            # Serialize first-key creation per tenant without a process lock.
            Organization.objects.select_for_update().get(pk=organization_id)
            existing = OrganizationDataKey.objects.filter(
                organization_id=organization_id,
                is_active=True,
            ).first()
            if existing is not None:
                return existing

            last = (
                OrganizationDataKey.objects.filter(organization_id=organization_id)
                .order_by("-version")
                .first()
            )
            version = (last.version + 1) if last is not None else 1
            dek = AESGCM.generate_key(bit_length=KEY_BYTES * 8)
            return OrganizationDataKey.objects.create(
                organization_id=organization_id,
                version=version,
                wrapped_dek=wrap_data_key(
                    dek,
                    organization_id,
                    version,
                    keyring.active_version,
                    keyring.kek(),
                ),
                kek_version=keyring.active_version,
                is_active=True,
            )
    except Organization.DoesNotExist:
        raise ConnectorCryptoError("Organization does not exist.") from None
    except IntegrityError:
        # A concurrent request won the partial-unique race.
        existing = OrganizationDataKey.objects.filter(
            organization_id=organization_id,
            is_active=True,
        ).first()
        if existing is not None:
            return existing
        raise ConnectorCryptoError(
            "Unable to initialize the connector data key."
        ) from None


def get_active_data_key(organization_id):
    """Return the organization's active DEK row, creating it if needed."""

    return _get_or_create_active_data_key(organization_id)


def encrypt_for_organization(
    organization_id,
    plaintext: str,
    aad: bytes,
) -> tuple[str, int]:
    """Encrypt a non-token secret with the organization's active DEK.

    Used for the PKCE verifier.  The caller supplies a purpose-bound AAD.
    """

    data_key = get_active_data_key(organization_id)
    dek = unwrap_data_key(data_key)
    return seal_secret(plaintext, dek, aad), data_key.version


def decrypt_for_organization(
    organization_id,
    ciphertext: str,
    key_version: int,
    aad: bytes,
) -> str:
    """Decrypt a secret written by ``encrypt_for_organization``."""

    from integrations.models import OrganizationDataKey

    try:
        data_key = OrganizationDataKey.objects.get(
            organization_id=organization_id,
            version=key_version,
        )
    except OrganizationDataKey.DoesNotExist:
        raise ConnectorDecryptionError(
            "The connector data key version is unavailable."
        ) from None

    return open_secret(ciphertext, unwrap_data_key(data_key), aad)


def encrypt_connection_tokens(
    organization_id,
    provider: str,
    external_account_id: str,
    access_token: str,
    refresh_token: str | None = None,
) -> EncryptedTokens:
    """Encrypt one connection's tokens with the organization DEK."""

    if not access_token:
        raise ValueError("access_token must not be empty.")
    if not provider:
        raise ValueError("provider must not be empty.")
    if not external_account_id:
        raise ValueError("external_account_id must not be empty.")

    data_key = get_active_data_key(organization_id)
    dek = unwrap_data_key(data_key)

    access_ciphertext = seal_secret(
        access_token,
        dek,
        token_aad(organization_id, provider, external_account_id, "access_token"),
    )
    refresh_ciphertext = ""
    if refresh_token:
        refresh_ciphertext = seal_secret(
            refresh_token,
            dek,
            token_aad(
                organization_id,
                provider,
                external_account_id,
                "refresh_token",
            ),
        )

    logger.debug(
        "connector_tokens_encrypted org=%s provider=%s account=%s key_version=%s",
        organization_id,
        provider,
        external_account_id,
        data_key.version,
    )
    return EncryptedTokens(
        access_token_ciphertext=access_ciphertext,
        refresh_token_ciphertext=refresh_ciphertext,
        key_version=data_key.version,
    )


def _data_key_for_connection(connection):
    from integrations.models import OrganizationDataKey

    try:
        return OrganizationDataKey.objects.get(
            organization_id=connection.organization_id,
            version=connection.key_version,
        )
    except OrganizationDataKey.DoesNotExist:
        raise ConnectorDecryptionError(
            "The connector data key version is unavailable."
        ) from None


def decrypt_token(connection, field: str) -> str:
    """Decrypt one token field of an ``OAuthConnection``."""

    if field not in TOKEN_FIELDS:
        raise ValueError(f"Unsupported token field: {field}")

    ciphertext = getattr(connection, f"{field}_ciphertext", "")
    if not ciphertext:
        if field == "refresh_token":
            return ""
        raise ConnectorDecryptionError("The connector token is missing.")

    data_key = _data_key_for_connection(connection)
    dek = unwrap_data_key(data_key)
    plaintext = open_secret(
        ciphertext,
        dek,
        token_aad(
            connection.organization_id,
            connection.provider,
            connection.external_account_id,
            field,
        ),
    )
    logger.debug(
        "connector_token_decrypted org=%s provider=%s account=%s field=%s key_version=%s",
        connection.organization_id,
        connection.provider,
        connection.external_account_id,
        field,
        connection.key_version,
    )
    return plaintext


def decrypt_connection_tokens(connection) -> tuple[str, str]:
    """Return ``(access_token, refresh_token)`` for a connection."""

    return (
        decrypt_token(connection, "access_token"),
        decrypt_token(connection, "refresh_token"),
    )
