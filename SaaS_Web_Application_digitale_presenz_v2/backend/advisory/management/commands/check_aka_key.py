"""Verify that the configured AKA key is honoured by the gateway.

A wrong or expired key does not produce a 401 on this gateway: it silently
serves the caller through the anonymous guest quota (3 requests/day, then a
429).  This command makes that state explicit and exits non-zero, so a
deployment or CI check can fail instead of discovering it from missing
recommendations.

Usage::

    python manage.py check_aka_key
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from advisory.services.aka_client import AkaAuthenticationError, AkaError
from advisory.services.factory import (
    build_aka_client,
    clear_aka_credentials_invalid,
    mark_aka_credentials_invalid,
)


class Command(BaseCommand):
    help = (
        "Send a one-token probe to the AKA gateway and fail if the request "
        "is served in anonymous guest mode (invalid/expired API key)."
    )

    def handle(self, *args, **options):
        try:
            client = build_aka_client()
        except Exception as exc:
            mark_aka_credentials_invalid(exc.__class__.__name__)
            raise CommandError(
                f"AKA client cannot be built: {exc.__class__.__name__}"
            ) from exc

        messages = [
            {"role": "user", "content": "Reply with the single word: pong"}
        ]
        try:
            with client:
                completion = client.chat(
                    messages, max_tokens=1, temperature=0
                )
        except AkaAuthenticationError as exc:
            mark_aka_credentials_invalid("invalid_api_key")
            raise CommandError(
                "AKA key is NOT authenticated: the gateway answered in guest "
                f"mode (HTTP {exc.status_code}). The advisor will refuse to "
                "serve AI until AKA_AI_API_KEY is fixed."
            ) from exc
        except AkaError as exc:
            # A provider outage is not proof of a bad key; do not poison the
            # shared cooldown marker.
            raise CommandError(
                f"AKA gateway unreachable or failing: {exc.__class__.__name__}"
            ) from exc

        clear_aka_credentials_invalid()
        self.stdout.write(
            self.style.SUCCESS(
                f"AKA credentials OK — authenticated call succeeded "
                f"(model={completion.model or 'unknown'}, "
                f"latency={completion.latency_ms} ms)"
            )
        )
