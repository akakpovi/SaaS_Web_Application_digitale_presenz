"""Authentification par clé d'API (offres ``can_use_api``)."""

from __future__ import annotations

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from subscriptions.models import ApiKey


class ApiKeyAuthentication(BaseAuthentication):
    """Accept ``Authorization: Api-Key pk_<prefix>_<secret>``."""

    keyword = b"api-key"

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != self.keyword:
            return None
        if len(parts) != 2:
            raise AuthenticationFailed("Invalid Api-Key header.")

        try:
            raw_key = parts[1].decode("utf-8")
            prefix = raw_key.split("_")[1]
        except (UnicodeDecodeError, IndexError):
            raise AuthenticationFailed("Malformed API key.") from None

        key = (
            ApiKey.objects.select_related("user")
            .filter(prefix=prefix, revoked_at__isnull=True)
            .first()
        )
        if key is None or not key.matches(raw_key):
            raise AuthenticationFailed("Invalid or revoked API key.")

        ApiKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
        return (key.user, key)

    def authenticate_header(self, request) -> str:
        return "Api-Key"
