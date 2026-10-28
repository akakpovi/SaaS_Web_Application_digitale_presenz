"""OAuth provider clients."""

from __future__ import annotations

from .base import OAuthProviderError, UnsupportedProviderError
from .linkedin import LinkedInOAuthClient


def get_provider_client(provider: str):
    normalized = (provider or "").strip().lower()
    if normalized == LinkedInOAuthClient.provider:
        return LinkedInOAuthClient()
    raise UnsupportedProviderError("Unsupported OAuth provider.")


__all__ = (
    "OAuthProviderError",
    "UnsupportedProviderError",
    "LinkedInOAuthClient",
    "get_provider_client",
)
