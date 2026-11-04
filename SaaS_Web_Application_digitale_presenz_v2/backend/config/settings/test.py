"""Settings used exclusively by the automated test suite.

The suite must stay runnable whatever the local ``.env`` selects. Production
security switches such as ``SECURE_SSL_REDIRECT`` or secure-only cookies turn
every Django test-client request into a redirect / drop the session cookie,
which would break unrelated tests. We therefore inherit the production
configuration and only relax the request-redirect and cookie flags.

The production configuration itself is validated separately with
``python manage.py check --deploy``.
"""

import base64
import copy

from .production import *  # noqa: F403

DEBUG = False

# Deterministic, test-only KEKs.  They are public on purpose and must never be
# reused outside the test suite.  Two versions let the rotation tests prove
# that old ciphertext remains readable while new keys are introduced.
CONNECTOR_KEKS = {
    1: base64.b64encode(b"test-kek-v1-" + b"0" * 20).decode("ascii"),
    2: base64.b64encode(b"test-kek-v2-" + b"0" * 20).decode("ascii"),
}
CONNECTOR_KEK_ACTIVE_VERSION = 1

# Deterministic LinkedIn OAuth settings for the mocked flow tests.  No real
# network call is made: the provider client is patched in the tests.
LINKEDIN_CLIENT_ID = "test-linkedin-client"
LINKEDIN_CLIENT_SECRET = "test-linkedin-secret"
LINKEDIN_REDIRECT_URI = (
    "https://app.example/api/v1/social/oauth/linkedin/callback/"
)
LINKEDIN_OAUTH_REVOKE_URL = "https://linkedin.test/revoke"
LINKEDIN_OAUTH_SCOPES = "openid profile w_member_social"
LINKEDIN_OAUTH_TIMEOUT = 5
OAUTH_STATE_TTL_SECONDS = 600

# Test client requests are plain HTTP: disable the redirect so endpoints can be
# exercised directly. HSTS is also disabled (it is meaningless under tests).
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0

# The test client does not speak TLS: keep cookies usable under HTTP.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Outbound e-mail is written to ``django.core.mail.outbox``.  The default
# backend is real SMTP, so without this override the suite would try to open
# network connections (and hang or fail) whenever a test exercises the alert,
# verification or report e-mail paths.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# The advisor is opt-in and must never make a real provider or broker call
# from an unrelated test.  Advisory tests enable it explicitly.
AI_ADVISOR_ENABLED = False

# Raw report archives are opt-in during tests: dedicated tests override this
# with a temporary directory so the suite never writes into the checkout.
SCANNER_ARCHIVE_ENABLED = False

# Tool executions inside the unit suite are mocked: keep them single-pass by
# default so a test never launches an unmocked second Gobuster process.  The
# complementary-pass behaviour has dedicated tests with an explicit override.
SCANNER_CONFIG = copy.deepcopy(SCANNER_CONFIG)  # noqa: F405
SCANNER_CONFIG["gobuster"]["extra_wordlist"] = ""

# Tests must be isolated from the development Redis database.  A local cache
# also lets ``--parallel`` workers rate-limit independently instead of sharing
# one throttle bucket across processes.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "presence-tests",
    }
}
