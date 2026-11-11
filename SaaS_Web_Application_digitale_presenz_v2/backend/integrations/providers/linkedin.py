"""LinkedIn OAuth 2.0 client (authorization code + PKCE S256).

Network calls are isolated here so the flow tests can patch this client
without touching the state machine.  No response body, token or verifier is
logged; only HTTP status codes and safe error codes are emitted.
"""

from __future__ import annotations

import logging
from urllib.parse import quote, urlencode

import requests
from django.conf import settings

from .base import (
    ExternalIdentity,
    OAuthTokens,
    ProviderNotConfiguredError,
    ProviderRequestError,
)

logger = logging.getLogger("integrations.oauth.linkedin")


class LinkedInOAuthClient:
    provider = "linkedin"

    def __init__(self) -> None:
        self.client_id = str(getattr(settings, "LINKEDIN_CLIENT_ID", "")).strip()
        self.client_secret = str(
            getattr(settings, "LINKEDIN_CLIENT_SECRET", "")
        ).strip()
        self.redirect_uri = str(getattr(settings, "LINKEDIN_REDIRECT_URI", "")).strip()
        self.authorize_url = str(
            getattr(
                settings,
                "LINKEDIN_OAUTH_AUTHORIZE_URL",
                "https://www.linkedin.com/oauth/v2/authorization",
            )
        )
        self.token_url = str(
            getattr(
                settings,
                "LINKEDIN_OAUTH_TOKEN_URL",
                "https://www.linkedin.com/oauth/v2/accessToken",
            )
        )
        self.userinfo_url = str(
            getattr(
                settings,
                "LINKEDIN_OAUTH_USERINFO_URL",
                "https://api.linkedin.com/v2/userinfo",
            )
        )
        self.revoke_url = str(
            getattr(
                settings,
                "LINKEDIN_OAUTH_REVOKE_URL",
                "https://www.linkedin.com/oauth/v2/revoke",
            )
        )
        self.scopes = str(
            getattr(
                settings,
                "LINKEDIN_OAUTH_SCOPES",
                "openid profile w_member_social",
            )
        ).strip()
        try:
            self.timeout = float(getattr(settings, "LINKEDIN_OAUTH_TIMEOUT", 10))
        except (TypeError, ValueError):
            self.timeout = 10.0

    def _require_configured(self) -> None:
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise ProviderNotConfiguredError("LinkedIn OAuth is not configured.")

    def authorization_url(self, state: str, code_challenge: str) -> str:
        self._require_configured()
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": self.scopes,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.authorize_url}?{urlencode(params, quote_via=quote)}"

    def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> OAuthTokens:
        self._require_configured()
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code_verifier": code_verifier,
        }
        try:
            response = requests.post(
                self.token_url,
                data=payload,
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
        except requests.RequestException:
            logger.warning("linkedin_oauth_exchange_transport_error")
            raise ProviderRequestError("LinkedIn token exchange failed.") from None

        if response.status_code < 200 or response.status_code >= 300:
            logger.warning(
                "linkedin_oauth_exchange_rejected status=%s",
                response.status_code,
            )
            raise ProviderRequestError("LinkedIn token exchange failed.")

        try:
            data = response.json()
        except ValueError:
            logger.warning("linkedin_oauth_exchange_invalid_json")
            raise ProviderRequestError("LinkedIn token exchange failed.") from None
        if not isinstance(data, dict):
            logger.warning("linkedin_oauth_exchange_invalid_payload")
            raise ProviderRequestError("LinkedIn token exchange failed.")

        access_token = str(data.get("access_token") or "").strip()
        if not access_token:
            logger.warning("linkedin_oauth_exchange_missing_access_token")
            raise ProviderRequestError("LinkedIn token exchange failed.")

        expires_in = data.get("expires_in")
        try:
            expires_in = int(expires_in) if expires_in is not None else None
        except (TypeError, ValueError):
            expires_in = None

        return OAuthTokens(
            access_token=access_token,
            refresh_token=str(data.get("refresh_token") or "").strip(),
            expires_in=expires_in if expires_in and expires_in > 0 else None,
            scope=str(data.get("scope") or "").strip(),
        )

    def refresh_access_token(self, *, refresh_token: str) -> OAuthTokens:
        """Exchange a refresh token for a new access token.

        LinkedIn uses the standard OAuth 2.0 refresh grant at the same token
        endpoint as the authorization-code exchange.  Some providers rotate
        refresh tokens; the caller decides whether to persist the returned one
        or retain the existing value when the response omits it.
        """

        self._require_configured()
        if not refresh_token:
            raise ProviderRequestError("LinkedIn token refresh failed.")

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        try:
            response = requests.post(
                self.token_url,
                data=payload,
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
        except requests.RequestException:
            logger.warning("linkedin_oauth_refresh_transport_error")
            raise ProviderRequestError("LinkedIn token refresh failed.") from None

        if response.status_code < 200 or response.status_code >= 300:
            logger.warning(
                "linkedin_oauth_refresh_rejected status=%s",
                response.status_code,
            )
            raise ProviderRequestError("LinkedIn token refresh failed.")

        try:
            data = response.json()
        except ValueError:
            logger.warning("linkedin_oauth_refresh_invalid_json")
            raise ProviderRequestError("LinkedIn token refresh failed.") from None
        if not isinstance(data, dict):
            logger.warning("linkedin_oauth_refresh_invalid_payload")
            raise ProviderRequestError("LinkedIn token refresh failed.")

        access_token = str(data.get("access_token") or "").strip()
        if not access_token:
            logger.warning("linkedin_oauth_refresh_missing_access_token")
            raise ProviderRequestError("LinkedIn token refresh failed.")

        expires_in = data.get("expires_in")
        try:
            expires_in = int(expires_in) if expires_in is not None else None
        except (TypeError, ValueError):
            expires_in = None

        return OAuthTokens(
            access_token=access_token,
            refresh_token=str(data.get("refresh_token") or "").strip(),
            expires_in=expires_in if expires_in and expires_in > 0 else None,
            scope=str(data.get("scope") or "").strip(),
        )

    def revoke_token(self, *, access_token: str) -> None:
        """Ask LinkedIn to invalidate an access token.

        LinkedIn implements RFC 7009-style revocation at
        ``/oauth/v2/revoke``.  Only the HTTP status is logged; the token and
        the provider response body are never written to a log line.
        """

        self._require_configured()
        if not access_token:
            raise ProviderRequestError("LinkedIn token revocation failed.")

        payload = {
            "token": access_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        try:
            response = requests.post(
                self.revoke_url,
                data=payload,
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
        except requests.RequestException:
            logger.warning("linkedin_oauth_revoke_transport_error")
            raise ProviderRequestError("LinkedIn token revocation failed.") from None

        if response.status_code < 200 or response.status_code >= 300:
            logger.warning(
                "linkedin_oauth_revoke_rejected status=%s",
                response.status_code,
            )
            raise ProviderRequestError("LinkedIn token revocation failed.")

    def fetch_identity(self, *, access_token: str) -> ExternalIdentity:
        self._require_configured()
        try:
            response = requests.get(
                self.userinfo_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=self.timeout,
            )
        except requests.RequestException:
            logger.warning("linkedin_oauth_userinfo_transport_error")
            raise ProviderRequestError("LinkedIn identity lookup failed.") from None

        if response.status_code < 200 or response.status_code >= 300:
            logger.warning(
                "linkedin_oauth_userinfo_rejected status=%s",
                response.status_code,
            )
            raise ProviderRequestError("LinkedIn identity lookup failed.")

        try:
            data = response.json()
        except ValueError:
            logger.warning("linkedin_oauth_userinfo_invalid_json")
            raise ProviderRequestError("LinkedIn identity lookup failed.") from None
        if not isinstance(data, dict):
            logger.warning("linkedin_oauth_userinfo_invalid_payload")
            raise ProviderRequestError("LinkedIn identity lookup failed.")

        subject = str(data.get("sub") or data.get("id") or "").strip()
        if not subject or len(subject) > 255:
            logger.warning("linkedin_oauth_userinfo_missing_subject")
            raise ProviderRequestError("LinkedIn identity lookup failed.")

        display_name = str(data.get("name") or "").strip()
        if not display_name:
            display_name = " ".join(
                part
                for part in (
                    str(data.get("given_name") or "").strip(),
                    str(data.get("family_name") or "").strip(),
                )
                if part
            )

        return ExternalIdentity(
            subject=subject,
            display_name=display_name,
            email=str(data.get("email") or "").strip(),
        )
