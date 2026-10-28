"""Provider-neutral OAuth value objects and errors."""

from __future__ import annotations

from dataclasses import dataclass


class OAuthProviderError(Exception):
    """Base class for provider failures; messages never contain tokens."""


class ProviderNotConfiguredError(OAuthProviderError):
    """The provider credentials or redirect URI are missing."""


class ProviderRequestError(OAuthProviderError):
    """The provider rejected or could not complete a request."""


class UnsupportedProviderError(OAuthProviderError):
    """The requested provider has no implementation."""


@dataclass(frozen=True)
class OAuthTokens:
    access_token: str
    refresh_token: str = ""
    expires_in: int | None = None
    scope: str = ""


@dataclass(frozen=True)
class ExternalIdentity:
    subject: str
    display_name: str = ""
    email: str = ""
