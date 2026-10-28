from __future__ import annotations

import base64
import hashlib
from datetime import timedelta
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlencode, urlparse

from django.conf import settings
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from integrations.models import OAuthConnection, OAuthState
from integrations.providers.base import (
    ExternalIdentity,
    OAuthTokens,
    ProviderRequestError,
)
from integrations.services.encryption import (
    ConnectorDecryptionError,
    decrypt_connection_tokens,
    decrypt_for_organization,
    state_aad,
)
from organizations.models import Membership, Organization


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    LINKEDIN_CLIENT_ID="test-client-id",
    LINKEDIN_CLIENT_SECRET="test-client-secret",
    LINKEDIN_REDIRECT_URI=(
        "https://app.example/api/v1/social/oauth/linkedin/callback/"
    ),
    OAUTH_STATE_TTL_SECONDS=600,
    FRONTEND_URL="https://app.example",
)
class OAuthFlowAPITests(APITestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            "oauth-owner@example.com",
            "Password123!",
        )
        self.viewer = User.objects.create_user(
            "oauth-viewer@example.com",
            "Password123!",
        )
        self.outsider = User.objects.create_user(
            "oauth-outsider@example.com",
            "Password123!",
        )

        self.organization = Organization.objects.create(
            name="OAuth Tenant A",
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
            user=self.viewer,
            role=Membership.Role.VIEWER,
        )

        self.other_organization = Organization.objects.create(
            name="OAuth Tenant B",
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

    def _authorize(
        self,
        *,
        organization: Organization | None = None,
        provider: str = "linkedin",
        user: User | None = None,
    ):
        organization = organization or self.organization
        self._auth(user or self.owner)
        return self.client.get(
            f"/api/v1/organizations/{organization.id}/social/connections/"
            f"{provider}/authorize/"
        )

    def _raw_state(self, response) -> str:
        query = parse_qs(
            urlparse(response.data["authorization_url"]).query
        )
        return query["state"][0]

    def _query(self, response) -> dict[str, list[str]]:
        return parse_qs(urlparse(response.data["authorization_url"]).query)

    def _state_row(self, raw_state: str) -> OAuthState:
        return OAuthState.objects.get(
            state_hash=hashlib.sha256(
                raw_state.encode("utf-8")
            ).hexdigest()
        )

    def _verifier(self, state: OAuthState) -> str:
        return decrypt_for_organization(
            state.organization_id,
            state.code_verifier_ciphertext,
            state.code_verifier_key_version,
            state_aad(
                state.organization_id,
                state.provider,
                state.state_hash,
            ),
        )

    def _callback(
        self,
        raw_state: str,
        *,
        code: str = "mock-authorization-code",
        provider: str = "linkedin",
        authenticated_as: User | None = None,
    ):
        # A real provider redirect carries no bearer token.  Tests clear the
        # client's forced authentication unless a test explicitly needs one.
        self._auth(authenticated_as)
        query = urlencode({"code": code, "state": raw_state})
        return self.client.get(
            f"/api/v1/social/oauth/{provider}/callback/?{query}"
        )

    def _redirect_query(self, response) -> dict[str, list[str]]:
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        parsed = urlparse(response["Location"])
        self.assertEqual(f"{parsed.scheme}://{parsed.netloc}", "https://app.example")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["Referrer-Policy"], "no-referrer")

        query = parse_qs(parsed.query)
        self.assertEqual(query["integration"], ["linkedin"])
        self.assertNotIn("code", query)
        self.assertNotIn("state", query)
        self.assertNotIn("error_description", query)
        self.assertNotIn("access_token", query)
        self.assertNotIn("refresh_token", query)
        self.assertNotIn("code=", response["Location"])
        self.assertNotIn("state=", response["Location"])
        return query

    def _assert_success_redirect(self, response) -> None:
        query = self._redirect_query(response)
        self.assertEqual(query["status"], ["success"])
        self.assertNotIn("error", query)

    def _assert_error_redirect(
        self,
        response,
        expected: str = "auth_failed",
    ) -> None:
        query = self._redirect_query(response)
        self.assertEqual(query["error"], [expected])
        self.assertNotIn("status", query)

    def _mock_client(
        self,
        *,
        access_token: str = "mock-access-token-distinctive",
        refresh_token: str = "mock-refresh-token-distinctive",
        subject: str = "li-account-123",
    ) -> Mock:
        client = Mock()
        client.redirect_uri = settings.LINKEDIN_REDIRECT_URI
        client.exchange_code.return_value = OAuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600,
            scope="openid profile w_member_social",
        )
        client.fetch_identity.return_value = ExternalIdentity(
            subject=subject,
            display_name="Mock LinkedIn User",
            email="mock-linkedin@example.com",
        )
        return client

    # ── Authorize ───────────────────────────────────────────────────────

    def test_authorize_returns_pkce_url_and_stores_only_state_hash(self):
        response = self._authorize()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], "linkedin")
        self.assertEqual(response["Cache-Control"], "no-store")

        query = self._query(response)
        self.assertEqual(query["client_id"], ["test-client-id"])
        self.assertEqual(
            query["redirect_uri"],
            [settings.LINKEDIN_REDIRECT_URI],
        )
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertNotIn("code_verifier", query)
        self.assertNotIn("code_verifier", response.content.decode())

        raw_state = query["state"][0]
        state = self._state_row(raw_state)

        self.assertEqual(state.organization, self.organization)
        self.assertEqual(state.user, self.owner)
        self.assertEqual(state.provider, "linkedin")
        self.assertNotEqual(state.state_hash, raw_state)
        self.assertEqual(len(state.state_hash), 64)
        self.assertEqual(state.consumed_at, None)
        self.assertTrue(state.code_verifier_ciphertext)
        self.assertNotIn(
            self._verifier(state),
            state.code_verifier_ciphertext,
        )
        self.assertEqual(state.redirect_uri, settings.LINKEDIN_REDIRECT_URI)

        remaining = state.expires_at - timezone.now()
        self.assertGreaterEqual(remaining, timedelta(seconds=540))
        self.assertLessEqual(remaining, timedelta(seconds=660))

        verifier = self._verifier(state)
        self.assertGreaterEqual(len(verifier), 43)
        self.assertLessEqual(len(verifier), 128)
        expected_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode("ascii")).digest()
            )
            .rstrip(b"=")
            .decode("ascii")
        )
        self.assertEqual(query["code_challenge"], [expected_challenge])

    def test_code_verifier_is_bound_to_state_and_tenant(self):
        authorization = self._authorize()
        raw_state = self._raw_state(authorization)
        state = self._state_row(raw_state)

        with self.assertRaises(ConnectorDecryptionError):
            decrypt_for_organization(
                state.organization_id,
                state.code_verifier_ciphertext,
                state.code_verifier_key_version,
                state_aad(
                    state.organization_id,
                    state.provider,
                    "0" * 64,
                ),
            )

        with self.assertRaises(ConnectorDecryptionError):
            decrypt_for_organization(
                state.organization_id,
                state.code_verifier_ciphertext,
                state.code_verifier_key_version,
                state_aad(
                    self.other_organization.id,
                    state.provider,
                    state.state_hash,
                ),
            )

    def test_viewer_cannot_start_authorization(self):
        response = self._authorize(user=self.viewer)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(OAuthState.objects.count(), 0)

    def test_outsider_gets_404_for_authorize(self):
        response = self._authorize(user=self.outsider)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(OAuthState.objects.count(), 0)

    def test_unauthenticated_authorize_is_rejected(self):
        self._auth(None)
        response = self.client.get(
            f"/api/v1/organizations/{self.organization.id}/social/connections/"
            "linkedin/authorize/"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unsupported_provider_is_rejected(self):
        response = self._authorize(provider="google")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "unsupported_provider")
        self.assertEqual(OAuthState.objects.count(), 0)

    @override_settings(LINKEDIN_CLIENT_ID="")
    def test_missing_provider_configuration_is_rejected(self):
        response = self._authorize()

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["error"], "provider_not_configured")
        self.assertEqual(OAuthState.objects.count(), 0)

    # ── Callback success ────────────────────────────────────────────────

    def test_callback_completes_mocked_linkedin_flow_without_leaking_secrets(self):
        authorization = self._authorize()
        raw_state = self._raw_state(authorization)
        state = self._state_row(raw_state)
        verifier = self._verifier(state)
        client = self._mock_client()

        with patch(
            "integrations.services.oauth.get_provider_client",
            return_value=client,
        ):
            response = self._callback(raw_state)

        self._assert_success_redirect(response)

        connection = OAuthConnection.objects.get(
            organization=self.organization,
            provider="linkedin",
            external_account_id="li-account-123",
        )
        self.assertEqual(
            decrypt_connection_tokens(connection),
            (
                "mock-access-token-distinctive",
                "mock-refresh-token-distinctive",
            ),
        )

        location = response["Location"]
        content = response.content.decode()
        for secret in (
            "mock-access-token-distinctive",
            "mock-refresh-token-distinctive",
            connection.access_token_ciphertext,
            connection.refresh_token_ciphertext,
            "code_verifier",
        ):
            self.assertNotIn(secret, location)
            self.assertNotIn(secret, content)
        self.assertNotIn("access_token_ciphertext", content)
        self.assertNotIn("refresh_token_ciphertext", content)

        state.refresh_from_db()
        self.assertIsNotNone(state.consumed_at)

        client.exchange_code.assert_called_once()
        call = client.exchange_code.call_args.kwargs
        self.assertEqual(call["code"], "mock-authorization-code")
        self.assertEqual(call["code_verifier"], verifier)
        self.assertEqual(call["redirect_uri"], settings.LINKEDIN_REDIRECT_URI)
        client.fetch_identity.assert_called_once_with(
            access_token="mock-access-token-distinctive"
        )

    def test_callback_upserts_existing_connection(self):
        first_state = self._raw_state(self._authorize())
        first_client = self._mock_client()
        with patch(
            "integrations.services.oauth.get_provider_client",
            return_value=first_client,
        ):
            first = self._callback(first_state)
        self._assert_success_redirect(first)

        existing = OAuthConnection.objects.get(
            organization=self.organization,
            provider="linkedin",
            external_account_id="li-account-123",
        )
        existing.refresh_failures = 3
        existing.status = OAuthConnection.Status.ERROR
        existing.save(update_fields=["refresh_failures", "status"])

        second_state = self._raw_state(self._authorize())
        second_client = self._mock_client(
            access_token="second-access-token",
            refresh_token="second-refresh-token",
        )
        with patch(
            "integrations.services.oauth.get_provider_client",
            return_value=second_client,
        ):
            second = self._callback(second_state)
        self._assert_success_redirect(second)

        self.assertEqual(
            OAuthConnection.objects.filter(
                organization=self.organization,
                provider="linkedin",
                external_account_id="li-account-123",
            ).count(),
            1,
        )
        connection = OAuthConnection.objects.get(
            organization=self.organization,
            provider="linkedin",
            external_account_id="li-account-123",
        )
        self.assertEqual(
            decrypt_connection_tokens(connection),
            ("second-access-token", "second-refresh-token"),
        )
        self.assertEqual(connection.refresh_failures, 0)
        self.assertEqual(connection.status, OAuthConnection.Status.ACTIVE)

    # ── State expiry, reuse and tenant binding ──────────────────────────

    def test_reused_state_is_rejected(self):
        raw_state = self._raw_state(self._authorize())
        client = self._mock_client()
        with patch(
            "integrations.services.oauth.get_provider_client",
            return_value=client,
        ):
            first = self._callback(raw_state)
            second = self._callback(raw_state)

        self._assert_success_redirect(first)
        self._assert_error_redirect(second, "invalid_state")
        self.assertEqual(OAuthConnection.objects.count(), 1)

    def test_expired_state_is_rejected(self):
        raw_state = self._raw_state(self._authorize())
        state = self._state_row(raw_state)
        state.expires_at = timezone.now() - timedelta(seconds=1)
        state.save(update_fields=["expires_at"])
        client = self._mock_client()

        with patch(
            "integrations.services.oauth.get_provider_client",
            return_value=client,
        ):
            response = self._callback(raw_state)

        self._assert_error_redirect(response, "invalid_state")
        self.assertEqual(OAuthConnection.objects.count(), 0)
        state.refresh_from_db()
        self.assertIsNone(state.consumed_at)

    def test_state_is_bound_to_initiating_tenant(self):
        raw_state = self._raw_state(self._authorize())
        # Even if another tenant's session is present, the state row decides
        # where the connection is written.  It can never land in tenant B.
        client = self._mock_client()

        with patch(
            "integrations.services.oauth.get_provider_client",
            return_value=client,
        ):
            response = self._callback(
                raw_state,
                authenticated_as=self.outsider,
            )

        self._assert_success_redirect(response)
        connection = OAuthConnection.objects.get(
            provider="linkedin",
            external_account_id="li-account-123",
        )
        self.assertEqual(connection.organization, self.organization)
        self.assertFalse(
            OAuthConnection.objects.filter(
                organization=self.other_organization
            ).exists()
        )

    def test_callback_works_without_bearer_token_like_provider_redirect(self):
        raw_state = self._raw_state(self._authorize())
        client = self._mock_client()

        with patch(
            "integrations.services.oauth.get_provider_client",
            return_value=client,
        ):
            response = self._callback(raw_state)

        self._assert_success_redirect(response)
        self.assertTrue(
            OAuthConnection.objects.filter(
                organization=self.organization,
                provider="linkedin",
                external_account_id="li-account-123",
            ).exists()
        )

    def test_missing_code_or_state_is_rejected(self):
        raw_state = self._raw_state(self._authorize())

        self._auth(None)
        no_code = self.client.get(
            "/api/v1/social/oauth/linkedin/callback/?"
            + urlencode({"state": raw_state})
        )
        no_state = self.client.get(
            "/api/v1/social/oauth/linkedin/callback/?"
            + urlencode({"code": "some-code"})
        )

        self._assert_error_redirect(no_code, "invalid_request")
        self._assert_error_redirect(no_state, "invalid_request")

    def test_provider_error_is_safe(self):
        self._auth(None)
        response = self.client.get(
            "/api/v1/social/oauth/linkedin/callback/?"
            + urlencode(
                {
                    "error": "access_denied",
                    "error_description": "provider-secret-description",
                }
            )
        )

        self._assert_error_redirect(response)
        self.assertNotIn(
            "provider-secret-description",
            response.content.decode(),
        )
        self.assertNotIn(
            "provider-secret-description",
            response["Location"],
        )

    @override_settings(
        FRONTEND_URL="https://app.example/app?tenant=presence&status=stale"
    )
    def test_redirect_preserves_frontend_path_and_drops_stale_status(self):
        self._auth(None)
        response = self.client.get(
            "/api/v1/social/oauth/linkedin/callback/"
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        parsed = urlparse(response["Location"])
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "app.example")
        self.assertEqual(parsed.path, "/app")
        query = parse_qs(parsed.query)
        self.assertEqual(query["tenant"], ["presence"])
        self.assertEqual(query["integration"], ["linkedin"])
        self.assertEqual(query["error"], ["invalid_request"])
        self.assertNotIn("status", query)

    @override_settings(FRONTEND_URL="")
    def test_missing_frontend_url_uses_safe_same_origin_fallback(self):
        self._auth(None)
        response = self.client.get(
            "/api/v1/social/oauth/linkedin/callback/"
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            response["Location"],
            "/?integration=linkedin&error=invalid_request",
        )
        self.assertNotIn("//", response["Location"])

    @override_settings(FRONTEND_URL="//attacker.example")
    def test_protocol_relative_frontend_url_falls_back_safely(self):
        self._auth(None)
        response = self.client.get(
            "/api/v1/social/oauth/linkedin/callback/"
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            response["Location"],
            "/?integration=linkedin&error=invalid_request",
        )
        self.assertNotIn("attacker.example", response["Location"])

    def test_unsupported_provider_redirect_uses_whitelisted_label(self):
        self._auth(None)
        response = self.client.get(
            "/api/v1/social/oauth/google/callback/?code=x&state=y"
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        query = parse_qs(urlparse(response["Location"]).query)
        self.assertEqual(query["integration"], ["unknown"])
        self.assertEqual(query["error"], ["unsupported_provider"])
        self.assertNotIn("google", response["Location"])

    def test_exchange_failure_consumes_state_and_redirects_with_error(self):
        raw_state = self._raw_state(self._authorize())
        state = self._state_row(raw_state)
        client = self._mock_client()
        client.exchange_code.side_effect = ProviderRequestError(
            "provider exchange failed"
        )

        with patch(
            "integrations.services.oauth.get_provider_client",
            return_value=client,
        ):
            response = self._callback(raw_state)
            retry = self._callback(raw_state)

        self._assert_error_redirect(response, "oauth_exchange_failed")
        self._assert_error_redirect(retry, "invalid_state")
        self.assertEqual(OAuthConnection.objects.count(), 0)
        state.refresh_from_db()
        self.assertIsNotNone(state.consumed_at)

    def test_identity_failure_redirects_without_creating_connection(self):
        raw_state = self._raw_state(self._authorize())
        client = self._mock_client()
        client.fetch_identity.side_effect = ProviderRequestError(
            "provider identity failed"
        )

        with patch(
            "integrations.services.oauth.get_provider_client",
            return_value=client,
        ):
            response = self._callback(raw_state)

        self._assert_error_redirect(response, "oauth_identity_failed")
        self.assertEqual(OAuthConnection.objects.count(), 0)
