import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

application = get_asgi_application()

# ASGI servers do not run Django system checks either; keep the same
# fail-closed startup contract as the WSGI entrypoint.
from integrations.checks import assert_connector_kek_configured  # noqa: E402

assert_connector_kek_configured()
