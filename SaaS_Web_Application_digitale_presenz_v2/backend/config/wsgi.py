import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_wsgi_application()

# WSGI servers do not run Django system checks.  Fail closed before gunicorn
# starts accepting requests when the connector KEK is missing or invalid.
from integrations.checks import assert_connector_kek_configured  # noqa: E402

assert_connector_kek_configured()
