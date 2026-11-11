from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from django.test import TestCase, override_settings

from integrations.providers.base import (
    ProviderNotConfiguredError,
    ProviderRequestError,
)
from integrations.providers.linkedin import LinkedInOAuthClient


@override_settings(
    LINKEDIN_CLIENT_ID="client-id",
    LINKEDIN_CLIENT_SECRET="client-secret",
    LINKEDIN_REDIRECT_URI="https://app.example/api/v1/social/oauth/linkedin/callback/",
    LINKEDIN_OAUTH_AUTHORIZE_URL="https://linkedin.test/authorize",
    LINKEDIN_OAUTH_TOKEN_URL="https://linkedin.test/token",
    LINKEDIN_OAUTH_USERINFO_URL="https://linkedin.test/userinfo",
    LINKEDIN_OAUTH_REVOKE_URL="https://linkedin.test/revoke",
    LINKEDIN_OAUTH_SCOPES="openid profile w_member_social",
    LINKEDIN_OAUTH_TIMEOUT=5,
)
class LinkedInOAuthClientTests(TestCase):
    @override_settings(
        LINKEDIN_OAUTH_AUTHORIZE_URL=(
            "https://www.linkedin.com/oauth/v2/authorization"
        ),
        LINKEDIN_OAUTH_TOKEN_URL=("https://www.linkedin.com/oauth/v2/accessToken"),
        LINKEDIN_OAUTH_USERINFO_URL="https://api.linkedin.com/v2/userinfo",
        LINKEDIN_OAUTH_REVOKE_URL=("https://www.linkedin.com/oauth/v2/revoke"),
    )
    def test_defaults_target_the_real_linkedin_endpoints(self):
        client = LinkedInOAuthClient()
        self.assertEqual(
            client.revoke_url,
            "https://www.linkedin.com/oauth/v2/revoke",
        )
        authorization = urlparse(
            client.authorization_url(
                state="state-value",
                code_challenge="challenge-value",
            )
        )

        self.assertEqual(authorization.scheme, "https")
        self.assertEqual(authorization.netloc, "www.linkedin.com")
        self.assertEqual(
            authorization.path,
            "/oauth/v2/authorization",
        )

        response = Mock(status_code=200)
        response.json.return_value = {"access_token": "real-endpoint-token"}
        with patch(
            "integrations.providers.linkedin.requests.post",
            return_value=response,
        ) as post:
            client.exchange_code(
                code="authorization-code",
                code_verifier="pkce-verifier",
                redirect_uri=(
                    "https://app.example/api/v1/social/oauth/linkedin/callback/"
                ),
            )

        self.assertEqual(
            post.call_args.args[0],
            "https://www.linkedin.com/oauth/v2/accessToken",
        )

        identity_response = Mock(status_code=200)
        identity_response.json.return_value = {"sub": "li-subject"}
        with patch(
            "integrations.providers.linkedin.requests.get",
            return_value=identity_response,
        ) as get:
            client.fetch_identity(access_token="real-endpoint-token")

        self.assertEqual(
            get.call_args.args[0],
            "https://api.linkedin.com/v2/userinfo",
        )

    @override_settings(LINKEDIN_CLIENT_SECRET="")
    def test_missing_secret_never_performs_a_network_call(self):
        with patch("integrations.providers.linkedin.requests.post") as post:
            with self.assertRaises(ProviderNotConfiguredError):
                LinkedInOAuthClient().exchange_code(
                    code="authorization-code",
                    code_verifier="pkce-verifier",
                    redirect_uri=(
                        "https://app.example/api/v1/social/oauth/linkedin/callback/"
                    ),
                )

        post.assert_not_called()

    def test_authorization_url_contains_pkce_parameters(self):
        url = LinkedInOAuthClient().authorization_url(
            state="state-value",
            code_challenge="challenge-value",
        )
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "linkedin.test")
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["client_id"], ["client-id"])
        self.assertEqual(query["state"], ["state-value"])
        self.assertEqual(query["code_challenge"], ["challenge-value"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(
            query["redirect_uri"],
            ["https://app.example/api/v1/social/oauth/linkedin/callback/"],
        )

    def test_exchange_sends_code_verifier_and_parses_tokens(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "expires_in": 3600,
            "scope": "openid profile w_member_social",
        }

        with patch(
            "integrations.providers.linkedin.requests.post",
            return_value=response,
        ) as post:
            tokens = LinkedInOAuthClient().exchange_code(
                code="authorization-code",
                code_verifier="pkce-verifier",
                redirect_uri=(
                    "https://app.example/api/v1/social/oauth/linkedin/callback/"
                ),
            )

        self.assertEqual(tokens.access_token, "mock-access-token")
        self.assertEqual(tokens.refresh_token, "mock-refresh-token")
        self.assertEqual(tokens.expires_in, 3600)
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://linkedin.test/token")
        self.assertEqual(kwargs["data"]["grant_type"], "authorization_code")
        self.assertEqual(kwargs["data"]["code"], "authorization-code")
        self.assertEqual(kwargs["data"]["code_verifier"], "pkce-verifier")
        self.assertEqual(kwargs["data"]["client_id"], "client-id")
        self.assertEqual(kwargs["data"]["client_secret"], "client-secret")
        self.assertEqual(
            kwargs["data"]["redirect_uri"],
            "https://app.example/api/v1/social/oauth/linkedin/callback/",
        )
        self.assertEqual(kwargs["timeout"], 5.0)

    def test_rejected_exchange_does_not_leak_provider_body(self):
        response = Mock(status_code=400)
        response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "provider-secret-description",
        }

        with patch(
            "integrations.providers.linkedin.requests.post",
            return_value=response,
        ):
            with self.assertRaises(ProviderRequestError) as captured:
                LinkedInOAuthClient().exchange_code(
                    code="authorization-code",
                    code_verifier="pkce-verifier",
                    redirect_uri=(
                        "https://app.example/api/v1/social/oauth/linkedin/callback/"
                    ),
                )

        self.assertNotIn(
            "provider-secret-description",
            str(captured.exception),
        )
        self.assertNotIn("mock-access-token", str(captured.exception))

    def test_fetch_identity_uses_bearer_token_and_parses_subject(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "sub": "li-subject-123",
            "name": "LinkedIn User",
            "email": "linkedin@example.com",
        }

        with patch(
            "integrations.providers.linkedin.requests.get",
            return_value=response,
        ) as get:
            identity = LinkedInOAuthClient().fetch_identity(
                access_token="mock-access-token"
            )

        self.assertEqual(identity.subject, "li-subject-123")
        self.assertEqual(identity.display_name, "LinkedIn User")
        self.assertEqual(identity.email, "linkedin@example.com")
        get.assert_called_once()
        args, kwargs = get.call_args
        self.assertEqual(args[0], "https://linkedin.test/userinfo")
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "Bearer mock-access-token",
        )

    def test_revoke_token_posts_client_credentials_and_token(self):
        response = Mock(status_code=200)

        with patch(
            "integrations.providers.linkedin.requests.post",
            return_value=response,
        ) as post:
            LinkedInOAuthClient().revoke_token(access_token="mock-access-token")

        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://linkedin.test/revoke")
        self.assertEqual(kwargs["data"]["token"], "mock-access-token")
        self.assertEqual(kwargs["data"]["client_id"], "client-id")
        self.assertEqual(kwargs["data"]["client_secret"], "client-secret")
        self.assertEqual(kwargs["timeout"], 5.0)

    def test_rejected_revocation_is_a_safe_provider_error(self):
        response = Mock(status_code=400)

        with patch(
            "integrations.providers.linkedin.requests.post",
            return_value=response,
        ):
            with self.assertRaises(ProviderRequestError) as captured:
                LinkedInOAuthClient().revoke_token(access_token="mock-access-token")

        self.assertNotIn("mock-access-token", str(captured.exception))
        self.assertNotIn("client-secret", str(captured.exception))

    def test_invalid_json_is_a_safe_provider_error(self):
        response = Mock(status_code=200)
        response.json.side_effect = ValueError("not json")

        with patch(
            "integrations.providers.linkedin.requests.post",
            return_value=response,
        ):
            with self.assertRaises(ProviderRequestError):
                LinkedInOAuthClient().exchange_code(
                    code="authorization-code",
                    code_verifier="pkce-verifier",
                    redirect_uri=(
                        "https://app.example/api/v1/social/oauth/linkedin/callback/"
                    ),
                )

    def test_refresh_exchange_uses_the_refresh_grant_and_parses_tokens(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "access_token": "refreshed-access-token",
            "refresh_token": "rotated-refresh-token",
            "expires_in": 7200,
            "scope": "openid profile w_member_social",
        }

        with patch(
            "integrations.providers.linkedin.requests.post",
            return_value=response,
        ) as post:
            tokens = LinkedInOAuthClient().refresh_access_token(
                refresh_token="old-refresh-token"
            )

        self.assertEqual(tokens.access_token, "refreshed-access-token")
        self.assertEqual(tokens.refresh_token, "rotated-refresh-token")
        self.assertEqual(tokens.expires_in, 7200)
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://linkedin.test/token")
        self.assertEqual(kwargs["data"]["grant_type"], "refresh_token")
        self.assertEqual(kwargs["data"]["refresh_token"], "old-refresh-token")
        self.assertEqual(kwargs["data"]["client_id"], "client-id")
        self.assertEqual(kwargs["data"]["client_secret"], "client-secret")
        self.assertEqual(kwargs["timeout"], 5.0)

    def test_rejected_refresh_is_a_safe_provider_error(self):
        response = Mock(status_code=400)
        response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "provider-secret-description",
        }

        with patch(
            "integrations.providers.linkedin.requests.post",
            return_value=response,
        ):
            with self.assertRaises(ProviderRequestError) as captured:
                LinkedInOAuthClient().refresh_access_token(
                    refresh_token="old-refresh-token"
                )

        self.assertNotIn(
            "provider-secret-description",
            str(captured.exception),
        )
        self.assertNotIn("old-refresh-token", str(captured.exception))
        self.assertNotIn("client-secret", str(captured.exception))

    def test_refresh_without_a_refresh_token_never_calls_the_provider(self):
        with patch("integrations.providers.linkedin.requests.post") as post:
            with self.assertRaises(ProviderRequestError):
                LinkedInOAuthClient().refresh_access_token(refresh_token="")

        post.assert_not_called()
