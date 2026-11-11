"""Rotate connector KEKs and/or per-organization DEKs.

Examples
--------
Rewrap every DEK under a new KEK without touching token ciphertext::

    python manage.py rotate_connector_keys --kek-version 2

Rotate both the KEK wrapping and every organization DEK, re-encrypting all
connection tokens::

    python manage.py rotate_connector_keys --kek-version 2 --rotate-dek
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from integrations.services.encryption import (
    ConnectorCryptoError,
    ConnectorKeyConfigurationError,
    get_keyring,
)
from integrations.services.rotation import (
    rewrap_all_data_keys,
    rotate_all_organizations,
)


class Command(BaseCommand):
    help = (
        "Rotate the connector KEK wrapping and optionally the per-organization "
        "DEKs.  Both operations are transactional."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--kek-version",
            type=int,
            default=None,
            help=(
                "Target KEK version (default: CONNECTOR_KEK_ACTIVE_VERSION). "
                "The version must already be present in the environment."
            ),
        )
        parser.add_argument(
            "--rotate-dek",
            action="store_true",
            help=(
                "Also generate a new DEK per organization and re-encrypt every "
                "OAuth connection.  Without this flag only the wrapping changes."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=200,
            help="Number of connections fetched per database batch (default: 200).",
        )

    def handle(self, *args, **options):
        if options["batch_size"] < 1:
            raise CommandError("--batch-size must be at least 1.")

        try:
            keyring = get_keyring()
            target = options["kek_version"] or keyring.active_version
            if target not in keyring.keys:
                raise CommandError(
                    f"CONNECTOR_KEK_V{target} is not configured; "
                    "add it to the environment before rotating."
                )

            if options["rotate_dek"]:
                results = rotate_all_organizations(
                    target,
                    batch_size=options["batch_size"],
                )
                connections = sum(result.connections_reencrypted for result in results)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Rotated {len(results)} organization DEK(s) under "
                        f"CONNECTOR_KEK_V{target}; re-encrypted {connections} "
                        "OAuth connection(s)."
                    )
                )
            else:
                count = rewrap_all_data_keys(target)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Re-wrapped {count} connector data key(s) under "
                        f"CONNECTOR_KEK_V{target}; token ciphertexts unchanged."
                    )
                )
        except ConnectorKeyConfigurationError as exc:
            raise CommandError(str(exc)) from None
        except ConnectorCryptoError as exc:
            raise CommandError(str(exc)) from None
