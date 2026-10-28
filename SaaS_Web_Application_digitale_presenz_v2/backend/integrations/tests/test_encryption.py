from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.test import TestCase

from integrations.services.encryption import (
    ConnectorDecryptionError,
    open_secret,
    seal_secret,
    token_aad,
)
from integrations.tests.utils import create_connection, make_org


class EnvelopeEncryptionTests(TestCase):
    def setUp(self):
        self.organization = make_org("Encryption")
        self.aad = token_aad(
            self.organization.id, "linkedin", "account-1", "access_token"
        )

    def test_encrypt_decrypt_round_trip(self):
        key = AESGCM.generate_key(bit_length=256)
        secret = "ya29.a0AfH6SMB-example-access-token"

        ciphertext = seal_secret(secret, key, self.aad)

        self.assertNotEqual(ciphertext, secret)
        self.assertTrue(ciphertext.startswith("v1."))
        self.assertEqual(open_secret(ciphertext, key, self.aad), secret)

    def test_ciphertext_does_not_contain_plaintext(self):
        key = AESGCM.generate_key(bit_length=256)
        secret = "refresh-token-with-a-very-distinctive-value"

        ciphertext = seal_secret(secret, key, self.aad)

        self.assertNotIn(secret, ciphertext)
        self.assertNotIn("refresh-token", ciphertext)

    def test_same_plaintext_uses_a_fresh_nonce(self):
        key = AESGCM.generate_key(bit_length=256)
        first = seal_secret("same-token", key, self.aad)
        second = seal_secret("same-token", key, self.aad)

        self.assertNotEqual(first, second)
        self.assertEqual(open_secret(first, key, self.aad), "same-token")
        self.assertEqual(open_secret(second, key, self.aad), "same-token")

    def test_tampered_ciphertext_fails_closed(self):
        key = AESGCM.generate_key(bit_length=256)
        ciphertext = seal_secret("tamper-me", key, self.aad)
        replacement = "A" if ciphertext[-1] != "A" else "B"
        tampered = ciphertext[:-1] + replacement

        with self.assertRaises(ConnectorDecryptionError):
            open_secret(tampered, key, self.aad)

    def test_wrong_key_fails_closed_without_leaking_secret(self):
        key = AESGCM.generate_key(bit_length=256)
        wrong_key = AESGCM.generate_key(bit_length=256)
        secret = "wrong-key-secret"
        ciphertext = seal_secret(secret, key, self.aad)

        with self.assertRaises(ConnectorDecryptionError) as captured:
            open_secret(ciphertext, wrong_key, self.aad)

        self.assertNotIn(secret, str(captured.exception))

    def test_connection_round_trip_through_models(self):
        access_token = "access-token-round-trip"
        refresh_token = "refresh-token-round-trip"
        connection = create_connection(
            self.organization,
            access_token=access_token,
            refresh_token=refresh_token,
        )

        from integrations.services.encryption import decrypt_connection_tokens

        self.assertEqual(
            decrypt_connection_tokens(connection),
            (access_token, refresh_token),
        )
        self.assertEqual(connection.key_version, 1)

    def test_missing_refresh_token_stays_empty(self):
        connection = create_connection(
            self.organization,
            access_token="access-only",
            refresh_token="",
        )

        from integrations.services.encryption import (
            decrypt_connection_tokens,
        )

        self.assertEqual(connection.refresh_token_ciphertext, "")
        self.assertEqual(
            decrypt_connection_tokens(connection),
            ("access-only", ""),
        )

    def test_model_string_never_contains_token_material(self):
        connection = create_connection(
            self.organization,
            access_token="string-secret",
            refresh_token="string-refresh",
        )

        rendered = str(connection)

        self.assertNotIn("string-secret", rendered)
        self.assertNotIn("string-refresh", rendered)
        self.assertNotIn(connection.access_token_ciphertext, rendered)
