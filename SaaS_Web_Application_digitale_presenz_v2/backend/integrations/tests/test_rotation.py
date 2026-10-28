from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from integrations.models import OAuthConnection, OrganizationDataKey
from integrations.services.encryption import decrypt_token
from integrations.services.mock_data import (
    count_mock_data,
    seed_mock_connector_data,
)
from integrations.tests.utils import create_connection, make_org


class RotationCommandTests(TestCase):
    def test_rotate_dek_over_mock_dataset_keeps_every_token_readable(self):
        mock_rows = seed_mock_connector_data(
            organizations=5,
            connections_per_org=12,
            prefix="rotation",
        )
        self.assertEqual(len(mock_rows), 60)
        self.assertEqual(count_mock_data("rotation"), (5, 60))

        ciphertext_before = {
            row.connection_id: OAuthConnection.objects.get(
                pk=row.connection_id
            ).access_token_ciphertext
            for row in mock_rows
        }

        output = StringIO()
        call_command(
            "rotate_connector_keys",
            "--kek-version",
            "2",
            "--rotate-dek",
            "--batch-size",
            "7",
            stdout=output,
        )

        self.assertIn("60", output.getvalue())
        for row in mock_rows:
            connection = OAuthConnection.objects.get(pk=row.connection_id)
            self.assertEqual(connection.key_version, 2)
            self.assertEqual(
                decrypt_token(connection, "access_token"),
                row.access_token,
            )
            self.assertEqual(
                decrypt_token(connection, "refresh_token"),
                row.refresh_token,
            )
            self.assertNotEqual(
                connection.access_token_ciphertext,
                ciphertext_before[row.connection_id],
            )

        organization_ids = {row.organization_id for row in mock_rows}
        self.assertEqual(len(organization_ids), 5)
        for organization_id in organization_ids:
            data_keys = list(
                OrganizationDataKey.objects.filter(
                    organization_id=organization_id
                ).order_by("version")
            )
            self.assertEqual([key.version for key in data_keys], [1, 2])
            self.assertFalse(data_keys[0].is_active)
            self.assertTrue(data_keys[1].is_active)
            self.assertEqual(data_keys[1].kek_version, 2)

    def test_kek_only_rotation_keeps_ciphertext_and_dek_version(self):
        organization = make_org("KEK only")
        access_token = "kek-only-access"
        refresh_token = "kek-only-refresh"
        connection = create_connection(
            organization,
            access_token=access_token,
            refresh_token=refresh_token,
        )
        old_ciphertext = connection.access_token_ciphertext
        data_key = OrganizationDataKey.objects.get(
            organization=organization,
            is_active=True,
        )
        old_wrapped_dek = data_key.wrapped_dek

        output = StringIO()
        call_command(
            "rotate_connector_keys",
            "--kek-version",
            "2",
            stdout=output,
        )

        connection.refresh_from_db()
        data_key.refresh_from_db()

        self.assertIn("Re-wrapped", output.getvalue())
        self.assertEqual(connection.access_token_ciphertext, old_ciphertext)
        self.assertEqual(connection.key_version, 1)
        self.assertEqual(data_key.kek_version, 2)
        self.assertNotEqual(data_key.wrapped_dek, old_wrapped_dek)
        self.assertEqual(
            decrypt_token(connection, "access_token"),
            access_token,
        )
        self.assertEqual(
            decrypt_token(connection, "refresh_token"),
            refresh_token,
        )

    def test_unknown_kek_version_aborts_without_touching_data(self):
        organization = make_org("Unknown KEK")
        connection = create_connection(
            organization,
            access_token="unchanged-access",
        )
        data_key = OrganizationDataKey.objects.get(
            organization=organization,
            is_active=True,
        )
        old_ciphertext = connection.access_token_ciphertext
        old_wrapped_dek = data_key.wrapped_dek

        with self.assertRaises(CommandError):
            call_command(
                "rotate_connector_keys",
                "--kek-version",
                "9",
                "--rotate-dek",
            )

        connection.refresh_from_db()
        data_key.refresh_from_db()
        self.assertEqual(connection.access_token_ciphertext, old_ciphertext)
        self.assertEqual(connection.key_version, 1)
        self.assertEqual(data_key.kek_version, 1)
        self.assertEqual(data_key.wrapped_dek, old_wrapped_dek)
        self.assertEqual(
            decrypt_token(connection, "access_token"),
            "unchanged-access",
        )

    def test_seed_command_creates_expected_rows(self):
        call_command(
            "seed_connector_mock_data",
            "--organizations",
            "2",
            "--connections-per-org",
            "3",
            "--prefix",
            "cli",
        )

        self.assertEqual(count_mock_data("cli"), (2, 6))
        self.assertEqual(
            OAuthConnection.objects.filter(
                organization__name__startswith="Mock Connector cli "
            ).count(),
            6,
        )
