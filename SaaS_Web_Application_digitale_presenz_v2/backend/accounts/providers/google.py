from dataclasses import dataclass
from typing import Protocol

from rest_framework.exceptions import APIException


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    email_verified: bool
    full_name: str = ""


class GoogleOAuthUnavailable(APIException):
    """Raised until a concrete Google token verifier is configured."""

    status_code = 501
    default_detail = "Google OAuth is not configured."
    default_code = "google_oauth_not_configured"


class GoogleOAuthProvider(Protocol):
    def verify_id_token(self, id_token: str) -> GoogleIdentity: ...


class UnconfiguredGoogleOAuthProvider:
    def verify_id_token(self, id_token: str) -> GoogleIdentity:
        raise GoogleOAuthUnavailable("Google OAuth is not configured.")
