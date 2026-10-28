from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from integrations.models import OAuthConnection
from integrations.providers.base import (
    ProviderNotConfiguredError,
    ProviderRequestError,
)
from integrations.tests.utils import create_connection
from organizations.models import Membership, Organization


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class OAuthConnectionManagementAPITests(APITestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            "connections-owner@example.com",
            "Password123!",
        )
        self.admin = User.objects.create_user(
            "connections-admin@example.com",
            "Password123!",
        )
        self.analyst = User.objects.create_user(
            "connections-analyst@example.com",
            "Password123!",
        )
        self.viewer = User.objects.create_user(
            "connections-viewer@example.com",
            "Password123!",
        )
        self.outsider = User.objects.create_user(
            "connections-outsider@example.com",
            "Password123!",
        )

        self.organization = Organization.objects.create(
            name="Connections Tenant A",
            billing_owner=self.owner,
            is_personal=False,
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=Membership.Role.OWNER,
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.admin,
            role=Membership.Role.ADMIN,
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.analyst,
            role=Membership.Role.ANALYST,
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.viewer,
            role=Membership.Role.VIEWER,
        )

        self.other_organization = Organization.objects.create(
            name="Connections Tenant B",
            billing_owner=self.outsider,
            is_personal=False,
        )
        Membership.objects.create(
            organization=self.other_organization,
            user=self.outsider,
            role=Membership.Role.OWNER,
        )

    def _auth(self, user: User | None) -> None:
        self.client.force_authenticate(user=user)

    def _list_url(self, organization: Organization | None = None) -> str:
        organization = organization or self.organization
        return (
            f"/api/v1/organizations/{organization.id}/social/connections/"
        )

    def _detail_url(
        self,
        connection: OAuthConnection,
        *,
        organization: Organization | None = None,
    ) -> str:
        organization = organization or self.organization
        return (
            f"/api/v1/organizations/{organization.id}/social/connections/"
            f"{connection.id}/"
        )

    def _results(self, response) -> list[dict]:
        data = response.data
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data

    # ── List ────────────────────────────────────────────────────────────

    def test_list_returns_only_current_tenant_and_no_secrets(self):
        connection = create_connection(
            self.organization,
            access_token="tenant-a-plaintext-token",
            refresh_token="tenant-a-refresh-token",
        )
        connection.expires_at = timezone.now() + timedelta(days=30)
        connection.save(update_fields=["expires_at"])
        other = create_connection(
            self.other_organization,
            access_token="tenant-b-plaintext-token",
        )

        self._auth(self.owner)
        response = self.client.get(self._list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Cache-Control"], "no-store")
        results = self._results(response)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], str(connection.id))
        self.assertEqual(results[0]["provider"], "linkedin")
        self.assertEqual(results[0]["status"], "active")
        self.assertIsNotNone(results[0]["expires_at"])
        self.assertEqual(
            set(results[0]),
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

        rendered = json.dumps(results, default=str)
        self.assertNotIn("tenant-a-plaintext-token", rendered)
        self.assertNotIn("tenant-a-refresh-token", rendered)
        self.assertNotIn(connection.access_token_ciphertext, rendered)
        self.assertNotIn(connection.refresh_token_ciphertext, rendered)
        self.assertNotIn("access_token_ciphertext", rendered)
        self.assertNotIn("refresh_token_ciphertext", rendered)
        self.assertNotIn(str(other.id), rendered)

    def test_viewer_can_list_but_outsider_and_anonymous_cannot(self):
        create_connection(self.organization)

        self._auth(self.viewer)
        viewer_response = self.client.get(self._list_url())
        self.assertEqual(viewer_response.status_code, status.HTTP_200_OK)

        self._auth(self.outsider)
        outsider_response = self.client.get(self._list_url())
        self.assertEqual(
            outsider_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self._auth(None)
        anonymous_response = self.client.get(self._list_url())
        self.assertEqual(
            anonymous_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # ── Delete ──────────────────────────────────────────────────────────

    def test_delete_revokes_provider_token_before_removing_row(self):
        connection = create_connection(
            self.organization,
            access_token="revoke-this-access-token",
        )
        client = Mock()

        def revoke_token(*, access_token: str) -> None:
            self.assertEqual(access_token, "revoke-this-access-token")
            # The local ciphertext must still exist while the provider call
            # is in flight; only a successful revocation permits deletion.
            self.assertTrue(
                OAuthConnection.objects.filter(pk=connection.pk).exists()
            )

        client.revoke_token.side_effect = revoke_token
        self._auth(self.owner)

        with patch(
            "integrations.services.connections.get_provider_client",
            return_value=client,
        ):
            response = self.client.delete(self._detail_url(connection))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.content, b"")
        self.assertFalse(
            OAuthConnection.objects.filter(pk=connection.pk).exists()
        )
        client.revoke_token.assert_called_once_with(
            access_token="revoke-this-access-token"
        )

    def test_delete_is_scoped_to_the_requested_tenant(self):
        other_connection = create_connection(self.other_organization)
        client = Mock()
        self._auth(self.owner)

        with patch(
            "integrations.services.connections.get_provider_client",
            return_value=client,
        ):
            response = self.client.delete(
                self._detail_url(
                    other_connection,
                    organization=self.organization,
                )
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            OAuthConnection.objects.filter(pk=other_connection.pk).exists()
        )
        client.revoke_token.assert_not_called()

    def test_admin_can_delete(self):
        connection = create_connection(self.organization)
        client = Mock()
        self._auth(self.admin)

        with patch(
            "integrations.services.connections.get_provider_client",
            return_value=client,
        ):
            response = self.client.delete(self._detail_url(connection))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            OAuthConnection.objects.filter(pk=connection.pk).exists()
        )
        client.revoke_token.assert_called_once()

    def test_analyst_and_viewer_cannot_delete(self):
        connection = create_connection(self.organization)
        client = Mock()

        for user in (self.analyst, self.viewer):
            self._auth(user)
            with patch(
                "integrations.services.connections.get_provider_client",
                return_value=client,
            ):
                response = self.client.delete(self._detail_url(connection))

            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            self.assertTrue(
                OAuthConnection.objects.filter(pk=connection.pk).exists()
            )

        client.revoke_token.assert_not_called()

    def test_provider_revocation_failure_keeps_connection(self):
        connection = create_connection(self.organization)
        client = Mock()
        client.revoke_token.side_effect = ProviderRequestError(
            "provider unavailable"
        )
        self._auth(self.owner)

        with patch(
            "integrations.services.connections.get_provider_client",
            return_value=client,
        ):
            response = self.client.delete(self._detail_url(connection))

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data["error"], "oauth_revocation_failed")
        self.assertTrue(
            OAuthConnection.objects.filter(pk=connection.pk).exists()
        )

    def test_missing_provider_configuration_keeps_connection(self):
        connection = create_connection(self.organization)
        client = Mock()
        client.revoke_token.side_effect = ProviderNotConfiguredError(
            "not configured"
        )
        self._auth(self.owner)

        with patch(
            "integrations.services.connections.get_provider_client",
            return_value=client,
        ):
            response = self.client.delete(self._detail_url(connection))

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data["error"], "oauth_revocation_failed")
        self.assertTrue(
            OAuthConnection.objects.filter(pk=connection.pk).exists()
        )

    def test_unauthenticated_delete_is_rejected(self):
        connection = create_connection(self.organization)
        client = Mock()
        self._auth(None)

        with patch(
            "integrations.services.connections.get_provider_client",
            return_value=client,
        ):
            response = self.client.delete(self._detail_url(connection))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(
            OAuthConnection.objects.filter(pk=connection.pk).exists()
        )
        client.revoke_token.assert_not_called()
