from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import Mock, patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from integrations.models import OAuthConnection
from integrations.providers.base import (
    ProviderNotConfiguredError,
    ProviderRequestError,
    OAuthTokens,
)
from integrations.services.encryption import decrypt_connection_tokens
from integrations.tasks import refresh_expiring_social_tokens
from integrations.tests.utils import create_connection, make_org


class RefreshExpiringTokensTests(TestCase):
    def setUp(self) -> None:
        self.organization = make_org("Refresh")
        self.connection = create_connection(
            self.organization,
            access_token="old-access-token",
            refresh_token="old-refresh-token",
        )
        self.connection.expires_at = timezone.now() + timedelta(hours=24)
        self.connection.save(update_fields=["expires_at"])

    def _set_expiry(self, connection, *, hours: int) -> None:
        connection.expires_at = timezone.now() + timedelta(hours=hours)
        connection.save(update_fields=["expires_at"])

    def _refresh_client(
        self,
        *,
        access_token: str = "new-access-token",
        refresh_token: str = "new-refresh-token",
        expires_in: int | None = 3600,
    ) -> Mock:
        client = Mock()
        client.refresh_access_token.return_value = OAuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )
        return client

    def test_due_linkedin_connection_is_refreshed_and_reencrypted(self):
        old_access_ciphertext = self.connection.access_token_ciphertext
        old_refresh_ciphertext = self.connection.refresh_token_ciphertext
        client = self._refresh_client()

        with patch(
            "integrations.services.refresh.get_provider_client",
            return_value=client,
        ):
            summary = refresh_expiring_social_tokens()

        self.assertEqual(summary["candidates"], 1)
        self.assertEqual(summary["refreshed"], 1)
        self.assertEqual(summary["failed"], 0)

        self.connection.refresh_from_db()
        self.assertEqual(
            decrypt_connection_tokens(self.connection),
            ("new-access-token", "new-refresh-token"),
        )
        self.assertNotEqual(
            self.connection.access_token_ciphertext,
            old_access_ciphertext,
        )
        self.assertNotEqual(
            self.connection.refresh_token_ciphertext,
            old_refresh_ciphertext,
        )
        self.assertGreater(
            self.connection.expires_at,
            timezone.now() + timedelta(minutes=30),
        )
        self.assertEqual(self.connection.status, OAuthConnection.Status.ACTIVE)
        self.assertEqual(self.connection.refresh_failures, 0)
        client.refresh_access_token.assert_called_once_with(
            refresh_token="old-refresh-token"
        )

    def test_provider_omitted_refresh_token_keeps_the_existing_one(self):
        client = self._refresh_client(
            access_token="rotated-access",
            refresh_token="",
        )

        with patch(
            "integrations.services.refresh.get_provider_client",
            return_value=client,
        ):
            summary = refresh_expiring_social_tokens()

        self.assertEqual(summary["refreshed"], 1)
        self.connection.refresh_from_db()
        self.assertEqual(
            decrypt_connection_tokens(self.connection),
            ("rotated-access", "old-refresh-token"),
        )

    def test_refresh_is_scoped_to_linkedin_and_the_72_hour_window(self):
        future = create_connection(
            self.organization,
            external_account_id="future-account",
            access_token="future-access-token",
            refresh_token="future-refresh-token",
        )
        self._set_expiry(future, hours=96)
        google = create_connection(
            self.organization,
            provider=OAuthConnection.Provider.GOOGLE,
            external_account_id="google-account",
            access_token="google-access-token",
            refresh_token="google-refresh-token",
        )
        self._set_expiry(google, hours=1)
        client = self._refresh_client()

        with patch(
            "integrations.services.refresh.get_provider_client",
            return_value=client,
        ):
            summary = refresh_expiring_social_tokens()

        self.assertEqual(summary["candidates"], 1)
        self.assertEqual(summary["refreshed"], 1)
        client.refresh_access_token.assert_called_once_with(
            refresh_token="old-refresh-token"
        )

        future.refresh_from_db()
        google.refresh_from_db()
        self.assertEqual(
            decrypt_connection_tokens(future),
            ("future-access-token", "future-refresh-token"),
        )
        self.assertEqual(
            decrypt_connection_tokens(google),
            ("google-access-token", "google-refresh-token"),
        )

    def test_two_tenants_are_refreshed_with_their_own_refresh_tokens(self):
        other_organization = make_org("Refresh Tenant B")
        other = create_connection(
            other_organization,
            access_token="tenant-b-old-access",
            refresh_token="tenant-b-old-refresh",
        )
        self._set_expiry(other, hours=12)

        def refresh(*, refresh_token: str) -> OAuthTokens:
            return OAuthTokens(
                access_token=f"rotated-{refresh_token}",
                refresh_token=f"next-{refresh_token}",
                expires_in=3600,
            )

        client = Mock()
        client.refresh_access_token.side_effect = refresh

        with patch(
            "integrations.services.refresh.get_provider_client",
            return_value=client,
        ):
            summary = refresh_expiring_social_tokens()

        self.assertEqual(summary["refreshed"], 2)
        self.connection.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(
            decrypt_connection_tokens(self.connection),
            ("rotated-old-refresh-token", "next-old-refresh-token"),
        )
        self.assertEqual(
            decrypt_connection_tokens(other),
            (
                "rotated-tenant-b-old-refresh",
                "next-tenant-b-old-refresh",
            ),
        )
        self.assertEqual(other.organization, other_organization)

    def test_missing_refresh_token_marks_an_expired_connection_without_network(self):
        self.connection.refresh_token_ciphertext = ""
        self.connection.expires_at = timezone.now() - timedelta(minutes=1)
        self.connection.save(update_fields=["refresh_token_ciphertext", "expires_at"])
        client = self._refresh_client()

        with patch(
            "integrations.services.refresh.get_provider_client",
            return_value=client,
        ):
            summary = refresh_expiring_social_tokens()

        self.assertEqual(summary["skipped"], 1)
        self.assertEqual(summary["reasons"]["missing_refresh_token"], 1)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.status, OAuthConnection.Status.EXPIRED)
        client.refresh_access_token.assert_not_called()

    def test_provider_failure_keeps_the_connection_usable_for_retry(self):
        old_ciphertext = self.connection.access_token_ciphertext
        client = Mock()
        client.refresh_access_token.side_effect = ProviderRequestError(
            "provider unavailable"
        )

        with patch(
            "integrations.services.refresh.get_provider_client",
            return_value=client,
        ):
            summary = refresh_expiring_social_tokens()

        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["reasons"]["provider_error"], 1)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.status, OAuthConnection.Status.ACTIVE)
        self.assertEqual(self.connection.refresh_failures, 1)
        self.assertEqual(
            self.connection.access_token_ciphertext,
            old_ciphertext,
        )
        self.assertEqual(
            decrypt_connection_tokens(self.connection),
            ("old-access-token", "old-refresh-token"),
        )

    def test_missing_provider_configuration_leaves_the_connection_eligible(self):
        client = Mock()
        client.refresh_access_token.side_effect = ProviderNotConfiguredError(
            "not configured"
        )

        with patch(
            "integrations.services.refresh.get_provider_client",
            return_value=client,
        ):
            summary = refresh_expiring_social_tokens()

        self.assertEqual(summary["failed"], 1)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.status, OAuthConnection.Status.ACTIVE)
        self.assertEqual(self.connection.refresh_failures, 0)

    def test_three_provider_failures_park_the_connection_and_stop_retries(self):
        client = Mock()
        client.refresh_access_token.side_effect = ProviderRequestError(
            "provider unavailable"
        )

        for expected_failures in range(1, 4):
            with patch(
                "integrations.services.refresh.get_provider_client",
                return_value=client,
            ):
                summary = refresh_expiring_social_tokens()

            self.assertEqual(summary["failed"], 1)
            self.connection.refresh_from_db()
            self.assertEqual(
                self.connection.refresh_failures,
                expected_failures,
            )
            self.assertEqual(
                self.connection.status,
                (
                    OAuthConnection.Status.ERROR
                    if expected_failures >= 3
                    else OAuthConnection.Status.ACTIVE
                ),
            )

        with patch(
            "integrations.services.refresh.get_provider_client",
            return_value=client,
        ):
            final = refresh_expiring_social_tokens()

        self.assertEqual(final["candidates"], 0)
        self.assertEqual(final["failed"], 0)
        self.assertEqual(client.refresh_access_token.call_count, 3)

    def test_success_resets_a_previous_failure_count(self):
        self.connection.refresh_failures = 2
        self.connection.save(update_fields=["refresh_failures"])
        client = self._refresh_client()

        with patch(
            "integrations.services.refresh.get_provider_client",
            return_value=client,
        ):
            summary = refresh_expiring_social_tokens()

        self.assertEqual(summary["refreshed"], 1)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.refresh_failures, 0)

    def test_task_and_refresh_logs_never_contain_tokens(self):
        client = self._refresh_client()

        with patch(
            "integrations.services.refresh.get_provider_client",
            return_value=client,
        ):
            with self.assertLogs("integrations.refresh", level="INFO") as captured:
                summary = refresh_expiring_social_tokens()

        output = "\n".join(captured.output)
        rendered_summary = json.dumps(summary, default=str)
        for secret in (
            "old-access-token",
            "old-refresh-token",
            "new-access-token",
            "new-refresh-token",
        ):
            self.assertNotIn(secret, output)
            self.assertNotIn(secret, rendered_summary)

        self.connection.refresh_from_db()
        self.assertNotIn(
            self.connection.access_token_ciphertext,
            output,
        )
        self.assertNotIn(
            self.connection.refresh_token_ciphertext,
            output,
        )

    def test_expired_access_token_is_still_recoverable(self):
        self.connection.expires_at = timezone.now() - timedelta(hours=2)
        self.connection.save(update_fields=["expires_at"])
        client = self._refresh_client()

        with patch(
            "integrations.services.refresh.get_provider_client",
            return_value=client,
        ):
            summary = refresh_expiring_social_tokens()

        self.assertEqual(summary["refreshed"], 1)

    @override_settings(SOCIAL_TOKEN_REFRESH_BATCH_SIZE=1)
    def test_batch_size_limits_work_per_run(self):
        second = create_connection(
            self.organization,
            external_account_id="second-due-account",
            access_token="second-access-token",
            refresh_token="second-refresh-token",
        )
        self._set_expiry(second, hours=2)
        self._set_expiry(self.connection, hours=1)
        client = self._refresh_client()

        with patch(
            "integrations.services.refresh.get_provider_client",
            return_value=client,
        ):
            summary = refresh_expiring_social_tokens()

        self.assertEqual(summary["candidates"], 1)
        self.assertEqual(summary["refreshed"], 1)
        client.refresh_access_token.assert_called_once()


class RefreshScheduleTests(TestCase):
    def test_refresh_task_is_in_the_beat_schedule(self):
        entry = settings.CELERY_BEAT_SCHEDULE["refresh-expiring-social-tokens"]

        self.assertEqual(
            entry["task"],
            "integrations.tasks.refresh_expiring_social_tokens",
        )
