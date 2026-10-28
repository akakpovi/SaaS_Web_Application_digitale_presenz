import base64
import json

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.test import TestCase, override_settings
from django.utils import timezone

from integrations.checks import check_connector_kek
from integrations.models import OAuthConnection, OAuthState
from integrations.serializers import (
    OAuthConnectionSerializer,
    OAuthStateSerializer,
)
from integrations.services.encryption import (
    ConnectorDecryptionError,
    ConnectorKeyConfigurationError,
    decrypt_connection_tokens,
    decrypt_token,
    encrypt_connection_tokens,
    get_keyring,
    open_secret,
    seal_secret,
    token_aad,
)
from integrations.tests.utils import create_connection, make_org


class AADBindingTests(TestCase):
    def setUp(self):
        self.org_a = make_org("Tenant A")
        self.org_b = make_org("Tenant B")
        self.dek = AESGCM.generate_key(bit_length=256)

    def test_organization_b_cannot_open_organization_a_ciphertext(self):
        secret = "tenant-a-access-token"
        ciphertext = seal_secret(
            secret,
            self.dek,
            token_aad(self.org_a.id, "linkedin", "account-1", "access_token"),
        )

        with self.assertRaises(ConnectorDecryptionError):
            open_secret(
                ciphertext,
                self.dek,
                token_aad(
                    self.org_b.id,
                    "linkedin",
                    "account-1",
                    "access_token",
                ),
            )

    def test_access_and_refresh_ciphertexts_are_not_interchangeable(self):
        secret = "field-bound-token"
        ciphertext = seal_secret(
            secret,
            self.dek,
            token_aad(self.org_a.id, "linkedin", "account-1", "access_token"),
        )

        with self.assertRaises(ConnectorDecryptionError):
            open_secret(
                ciphertext,
                self.dek,
                token_aad(
                    self.org_a.id,
                    "linkedin",
                    "account-1",
                    "refresh_token",
                ),
            )

    def test_copied_ciphertext_fails_in_another_tenant_row(self):
        connection_a = create_connection(
            self.org_a,
            external_account_id="same-account",
            access_token="tenant-a-secret",
        )
        connection_b = create_connection(
            self.org_b,
            external_account_id="same-account",
            access_token="tenant-b-secret",
        )

        connection_b.access_token_ciphertext = (
            connection_a.access_token_ciphertext
        )
        connection_b.key_version = connection_a.key_version
        connection_b.save(
            update_fields=["access_token_ciphertext", "key_version", "updated_at"]
        )

        with self.assertRaises(ConnectorDecryptionError):
            decrypt_token(connection_b, "access_token")


class SerializerAndLoggingTests(TestCase):
    def test_serializer_omits_ciphertext_and_plaintext(self):
        organization = make_org("Serializer")
        secret = "serializer-must-not-leak-this"
        connection = create_connection(
            organization,
            access_token=secret,
            refresh_token="serializer-refresh-secret",
        )

        data = OAuthConnectionSerializer(connection).data
        rendered = json.dumps(data, default=str)

        self.assertNotIn("access_token_ciphertext", data)
        self.assertNotIn("refresh_token_ciphertext", data)
        self.assertNotIn(secret, rendered)
        self.assertNotIn(connection.access_token_ciphertext, rendered)
        self.assertEqual(
            set(data),
            {
                "id",
                "organization",
                "provider",
                "external_account_id",
                "status",
                "expires_at",
                "created_at",
                "updated_at",
            },
        )

    def test_oauth_state_serializer_omits_state_hash(self):
        organization = make_org("State Serializer")
        state = OAuthState.objects.create(
            state_hash="a" * 64,
            organization=organization,
            user=organization.billing_owner,
            provider=OAuthConnection.Provider.GOOGLE,
            expires_at=timezone.now(),
        )

        data = OAuthStateSerializer(state).data
        rendered = json.dumps(data, default=str)

        self.assertNotIn("state_hash", data)
        self.assertNotIn(state.state_hash, rendered)

    def test_logs_never_contain_plaintext_or_ciphertext(self):
        organization = make_org("Logs")
        access_token = "log-access-token-distinctive"
        refresh_token = "log-refresh-token-distinctive"

        with self.assertLogs("integrations.crypto", level="DEBUG") as captured:
            encrypted = encrypt_connection_tokens(
                organization.id,
                OAuthConnection.Provider.LINKEDIN,
                "log-account",
                access_token,
                refresh_token,
            )
            connection = OAuthConnection.objects.create(
                organization=organization,
                provider=OAuthConnection.Provider.LINKEDIN,
                external_account_id="log-account",
                access_token_ciphertext=encrypted.access_token_ciphertext,
                refresh_token_ciphertext=encrypted.refresh_token_ciphertext,
                key_version=encrypted.key_version,
            )
            decrypt_connection_tokens(connection)

        output = "\n".join(captured.output)
        self.assertNotIn(access_token, output)
        self.assertNotIn(refresh_token, output)
        self.assertNotIn(encrypted.access_token_ciphertext, output)
        self.assertNotIn(encrypted.refresh_token_ciphertext, output)
        self.assertIn("connector_token", output)


class KeyConfigurationTests(TestCase):
    def test_missing_kek_blocks_startup(self):
        with override_settings(
            CONNECTOR_KEKS={},
            CONNECTOR_KEK_ACTIVE_VERSION=1,
        ):
            errors = check_connector_kek(None)

            self.assertEqual(
                [error.id for error in errors],
                ["integrations.E001"],
            )
            with self.assertRaises(ConnectorKeyConfigurationError):
                get_keyring()
            with self.assertRaises(ImproperlyConfigured):
                get_keyring()
            with self.assertRaises(SystemCheckError):
                call_command("check")

    def test_wrong_key_length_blocks_startup(self):
        with override_settings(
            CONNECTOR_KEKS={
                1: base64.b64encode(b"too-short").decode("ascii"),
            },
            CONNECTOR_KEK_ACTIVE_VERSION=1,
        ):
            errors = check_connector_kek(None)

            self.assertEqual(
                [error.id for error in errors],
                ["integrations.E001"],
            )
            with self.assertRaises(ConnectorKeyConfigurationError):
                get_keyring()

    def test_active_version_must_exist(self):
        valid_key = base64.b64encode(b"k" * 32).decode("ascii")
        with override_settings(
            CONNECTOR_KEKS={1: valid_key},
            CONNECTOR_KEK_ACTIVE_VERSION=2,
        ):
            errors = check_connector_kek(None)

            self.assertEqual(
                [error.id for error in errors],
                ["integrations.E001"],
            )
            with self.assertRaises(ConnectorKeyConfigurationError):
                get_keyring()

    def test_invalid_base64_key_blocks_startup(self):
        with override_settings(
            CONNECTOR_KEKS={1: "not-base64-!!!"},
            CONNECTOR_KEK_ACTIVE_VERSION=1,
        ):
            errors = check_connector_kek(None)

            self.assertEqual(
                [error.id for error in errors],
                ["integrations.E001"],
            )
            with self.assertRaises(ConnectorKeyConfigurationError):
                get_keyring()
