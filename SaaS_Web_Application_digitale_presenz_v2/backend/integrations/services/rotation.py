"""Key rotation for the connector token vault.

Two operations are deliberately separate:

* ``rewrap_all_data_keys`` rotates only the KEK wrapping.  Token ciphertexts
  and ``OAuthConnection.key_version`` values stay untouched.
* ``rotate_organization_dek`` creates a fresh DEK, re-encrypts every connection
  of the organization under it, then switches the active key.  The whole
  organization rotation is one transaction: a failure leaves the old key in
  place and the old ciphertexts readable.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.db import transaction
from django.utils import timezone

from integrations.models import OAuthConnection, Organization, OrganizationDataKey

from .encryption import (
    KEY_BYTES,
    ConnectorCryptoError,
    KeyRing,
    get_keyring,
    open_secret,
    seal_secret,
    token_aad,
    unwrap_data_key,
    wrap_data_key,
)


@dataclass(frozen=True)
class OrganizationRotationResult:
    organization_id: UUID
    new_key_version: int
    connections_reencrypted: int


def rewrap_data_key(
    data_key: OrganizationDataKey,
    target_kek_version: int,
    keyring: KeyRing | None = None,
) -> None:
    """Re-wrap one DEK under ``target_kek_version`` without changing it."""

    keyring = keyring or get_keyring()
    dek = unwrap_data_key(data_key, keyring)
    data_key.wrapped_dek = wrap_data_key(
        dek,
        data_key.organization_id,
        data_key.version,
        target_kek_version,
        keyring.kek(target_kek_version),
    )
    data_key.kek_version = target_kek_version
    data_key.rotated_at = timezone.now()
    data_key.save(update_fields=["wrapped_dek", "kek_version", "rotated_at"])


def rewrap_all_data_keys(target_kek_version: int) -> int:
    """Re-wrap every stored DEK, including historical versions."""

    keyring = get_keyring()
    target_kek = keyring.kek(target_kek_version)
    count = 0
    data_key_ids = list(
        OrganizationDataKey.objects.order_by("organization_id", "version").values_list(
            "id", flat=True
        )
    )

    for data_key_id in data_key_ids:
        with transaction.atomic():
            data_key = (
                OrganizationDataKey.objects.select_for_update()
                .select_related("organization")
                .get(pk=data_key_id)
            )
            dek = unwrap_data_key(data_key, keyring)
            data_key.wrapped_dek = wrap_data_key(
                dek,
                data_key.organization_id,
                data_key.version,
                target_kek_version,
                target_kek,
            )
            data_key.kek_version = target_kek_version
            data_key.rotated_at = timezone.now()
            data_key.save(update_fields=["wrapped_dek", "kek_version", "rotated_at"])
        count += 1

    return count


def rotate_organization_dek(
    organization_id,
    target_kek_version: int,
    batch_size: int = 200,
) -> OrganizationRotationResult:
    """Rotate one organization's DEK and re-encrypt all its connections."""

    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")

    keyring = get_keyring()
    target_kek = keyring.kek(target_kek_version)

    with transaction.atomic():
        try:
            Organization.objects.select_for_update().get(pk=organization_id)
        except Organization.DoesNotExist:
            raise ConnectorCryptoError("Organization does not exist.") from None

        data_keys = list(
            OrganizationDataKey.objects.select_for_update()
            .filter(organization_id=organization_id)
            .order_by("version")
        )
        if not data_keys:
            raise ConnectorCryptoError(
                "The organization has no connector data key to rotate."
            )

        active_key = next((key for key in data_keys if key.is_active), None)
        if active_key is None:
            raise ConnectorCryptoError(
                "The organization has no active connector data key."
            )

        new_version = max(key.version for key in data_keys) + 1
        new_dek = AESGCM.generate_key(bit_length=KEY_BYTES * 8)
        new_key = OrganizationDataKey.objects.create(
            organization_id=organization_id,
            version=new_version,
            wrapped_dek=wrap_data_key(
                new_dek,
                organization_id,
                new_version,
                target_kek_version,
                target_kek,
            ),
            kek_version=target_kek_version,
            is_active=False,
        )

        keys_by_version = {key.version: key for key in data_keys}
        connections = (
            OAuthConnection.objects.select_for_update()
            .filter(organization_id=organization_id)
            .order_by("id")
        )

        reencrypted = 0
        for connection in connections.iterator(chunk_size=batch_size):
            old_key = keys_by_version.get(connection.key_version)
            if old_key is None:
                raise ConnectorCryptoError(
                    "A connection references a missing connector data key."
                )
            old_dek = unwrap_data_key(old_key, keyring)

            access_token = open_secret(
                connection.access_token_ciphertext,
                old_dek,
                token_aad(
                    connection.organization_id,
                    connection.provider,
                    connection.external_account_id,
                    "access_token",
                ),
            )
            refresh_token = ""
            if connection.refresh_token_ciphertext:
                refresh_token = open_secret(
                    connection.refresh_token_ciphertext,
                    old_dek,
                    token_aad(
                        connection.organization_id,
                        connection.provider,
                        connection.external_account_id,
                        "refresh_token",
                    ),
                )

            connection.access_token_ciphertext = seal_secret(
                access_token,
                new_dek,
                token_aad(
                    connection.organization_id,
                    connection.provider,
                    connection.external_account_id,
                    "access_token",
                ),
            )
            connection.refresh_token_ciphertext = (
                seal_secret(
                    refresh_token,
                    new_dek,
                    token_aad(
                        connection.organization_id,
                        connection.provider,
                        connection.external_account_id,
                        "refresh_token",
                    ),
                )
                if refresh_token
                else ""
            )
            connection.key_version = new_version
            connection.save(
                update_fields=[
                    "access_token_ciphertext",
                    "refresh_token_ciphertext",
                    "key_version",
                    "updated_at",
                ]
            )
            reencrypted += 1

        # Switch the active marker only after every row has been migrated.
        active_key.is_active = False
        active_key.rotated_at = timezone.now()
        active_key.save(update_fields=["is_active", "rotated_at"])
        new_key.is_active = True
        new_key.save(update_fields=["is_active"])

        # Historical DEKs stay readable under the new KEK as well.  This is
        # what makes a later KEK-only rotation and emergency rollback safe.
        for data_key in data_keys:
            dek = unwrap_data_key(data_key, keyring)
            data_key.wrapped_dek = wrap_data_key(
                dek,
                data_key.organization_id,
                data_key.version,
                target_kek_version,
                target_kek,
            )
            data_key.kek_version = target_kek_version
            data_key.rotated_at = timezone.now()
            data_key.save(update_fields=["wrapped_dek", "kek_version", "rotated_at"])

    return OrganizationRotationResult(
        organization_id=organization_id,
        new_key_version=new_version,
        connections_reencrypted=reencrypted,
    )


def rotate_all_organizations(
    target_kek_version: int,
    batch_size: int = 200,
) -> list[OrganizationRotationResult]:
    """Rotate the DEK of every organization that has one."""

    organization_ids = list(
        OrganizationDataKey.objects.filter(is_active=True)
        .order_by("organization_id")
        .values_list("organization_id", flat=True)
        .distinct()
    )
    return [
        rotate_organization_dek(
            organization_id,
            target_kek_version,
            batch_size=batch_size,
        )
        for organization_id in organization_ids
    ]
