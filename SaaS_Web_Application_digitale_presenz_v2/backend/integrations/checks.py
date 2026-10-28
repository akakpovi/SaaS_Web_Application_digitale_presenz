"""Startup checks for the connector token vault.

Django runs system checks before ``runserver``, ``migrate`` and most
management commands.  Returning an ``Error`` here is therefore the supported
way to make a misconfigured deployment fail closed instead of silently
starting with an empty key ring.
"""

from __future__ import annotations

from django.core.checks import Error, register

from .services.encryption import ConnectorKeyConfigurationError, get_keyring


def assert_connector_kek_configured() -> None:
    """Raise if the key ring is unusable.

    WSGI/ASGI servers do not run Django system checks, so they call this
    explicitly before accepting traffic.
    """

    get_keyring()


@register()
def check_connector_kek(app_configs, **kwargs):
    try:
        get_keyring()
    except ConnectorKeyConfigurationError as exc:
        return [
            Error(
                str(exc),
                hint=(
                    "Generate a 32-byte key with `openssl rand -base64 32`, "
                    "set CONNECTOR_KEK_V1, and keep the previous KEKs available "
                    "while a rotation is in progress."
                ),
                id="integrations.E001",
            )
        ]
    return []
