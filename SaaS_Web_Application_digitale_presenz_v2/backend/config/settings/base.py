"""Shared Django configuration for all environments."""

import os
from pathlib import Path
from typing import Final

from pythonjsonlogger.json import JsonFormatter

BASE_DIR: Final = Path(__file__).resolve().parents[2]


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).lower() in {"1", "true", "yes", "on"}


SECRET_KEY = env("DJANGO_SECRET_KEY", "unsafe-development-only-secret-key")
DEBUG = env_bool("DJANGO_DEBUG")


# ---- Social connector token vault ---------------------------------------
# KEKs are read from the environment only, one base64-encoded 32-byte key per
# version (CONNECTOR_KEK_V1, CONNECTOR_KEK_V2, ...).  Keeping several versions
# available is what allows a manual rotation to decrypt rows written under the
# previous key.  The system check in integrations.checks fails closed when no
# usable key is configured.
def _connector_keks_from_env() -> dict[int, str]:
    prefix = "CONNECTOR_KEK_V"
    keys: dict[int, str] = {}
    for name, value in os.environ.items():
        if not name.startswith(prefix):
            continue
        suffix = name[len(prefix):]
        if not suffix.isdigit():
            continue
        if value and value.strip():
            keys[int(suffix)] = value.strip()
    return keys


CONNECTOR_KEKS = _connector_keks_from_env()
try:
    CONNECTOR_KEK_ACTIVE_VERSION = int(
        os.environ.get("CONNECTOR_KEK_ACTIVE_VERSION", "")
        or (max(CONNECTOR_KEKS) if CONNECTOR_KEKS else 0)
    )
except ValueError:
    # Keep startup deterministic; the integrations system check reports the
    # invalid configuration instead of raising a bare ValueError here.
    CONNECTOR_KEK_ACTIVE_VERSION = 0

ALLOWED_HOSTS = [host.strip() for host in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,web,testserver").split(",") if host.strip()]
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "rest_framework_simplejwt.token_blacklist",
    "core",
    "accounts",
    "organizations",
    "websites",
    "scans",
    "public_checker",
    "monitoring",
    "alerts",
    "notifications",
    "reports",
    "reviews",
    "subscriptions",
    "seo",
    "social",
    "advanced_security",
    "analytics",
    "advisory",
    "integrations",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "analytics.middleware.TrafficTrackingMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": env("POSTGRES_DB", "presence"),
    "USER": env("POSTGRES_USER", "presence"),
    "PASSWORD": env("POSTGRES_PASSWORD", "presence"),
    "HOST": env("POSTGRES_HOST", "localhost"),
    "PORT": env("POSTGRES_PORT", "5432"),
    "CONN_MAX_AGE": 60,
    "CONN_HEALTH_CHECKS": True,
}}

REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")
CACHES = {"default": {
    "BACKEND": "django_redis.cache.RedisCache",
    "LOCATION": REDIS_URL,
    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    "KEY_PREFIX": "presence",
}}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 600        # 10 min — covers even ZAP active scans
CELERY_TASK_SOFT_TIME_LIMIT = 570   # 9.5 min — soft limit for graceful shutdown
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE: dict[str, object] = {
    "purge_guest_data_nightly": {
        "task": "scans.tasks.purge_guest_data",
        "schedule": crontab(hour=3, minute=0),
    },
    "prune-scanner-archives-daily": {
        "task": "scans.tasks.prune_scanner_archives",
        "schedule": crontab(hour=3, minute=30),
    },
    "run-due-monitors": {
        "task": "monitoring.tasks.run_due_monitors",
        "schedule": crontab(minute="*/5"),
    },
    "cleanup-old-alerts": {
        "task": "alerts.tasks.cleanup_old_alerts",
        "schedule": crontab(hour=2, minute=0),
    },
    "expire-subscriptions-daily": {
        "task": "subscriptions.tasks.expire_subscriptions",
        "schedule": crontab(hour=2, minute=15),
    },
    "generate-monthly-reports": {
        "task": "reports.tasks.generate_monthly_reports",
        "schedule": crontab(day_of_month=1, hour=3, minute=0),
    },
    "refresh-expiring-social-tokens": {
        "task": "integrations.tasks.refresh_expiring_social_tokens",
        "schedule": crontab(hour="*/6", minute=15),
    },
}

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "subscriptions.authentication.ApiKeyAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "public_scan_create": "10/hour",
        "public_scan_poll": "120/minute",
        # The AI chat spends the project's model credits on every message: a
        # per-user ceiling keeps a stuck client or a malicious member from
        # draining the budget.  Overridable per deployment.
        "advisor_chat": env("AI_ADVISOR_CHAT_THROTTLE", "60/hour"),
    },
}
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]
SIMPLE_JWT = {
    "AUTH_HEADER_TYPES": ("Bearer",),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# VAPID keys for Web Push notifications
VAPID_PUBLIC_KEY = env("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS_SUB = env("VAPID_CLAIMS_SUB", "mailto:support@presence.local")

FRONTEND_URL = env("FRONTEND_URL", "http://localhost:8443").rstrip("/")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "noreply@presence.local")

# ---- Social OAuth (LinkedIn first) ---------------------------------------
# Secrets stay server-side.  The redirect URI is explicit and must exactly
# match the value registered in the LinkedIn developer portal; it is never
# derived from the request Host header.
LINKEDIN_CLIENT_ID = env("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = env("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_REDIRECT_URI = env(
    "LINKEDIN_REDIRECT_URI",
    f"{FRONTEND_URL}/api/v1/social/oauth/linkedin/callback/",
).strip()
LINKEDIN_OAUTH_AUTHORIZE_URL = env(
    "LINKEDIN_OAUTH_AUTHORIZE_URL",
    "https://www.linkedin.com/oauth/v2/authorization",
)
LINKEDIN_OAUTH_TOKEN_URL = env(
    "LINKEDIN_OAUTH_TOKEN_URL",
    "https://www.linkedin.com/oauth/v2/accessToken",
)
LINKEDIN_OAUTH_USERINFO_URL = env(
    "LINKEDIN_OAUTH_USERINFO_URL",
    "https://api.linkedin.com/v2/userinfo",
)
LINKEDIN_OAUTH_REVOKE_URL = env(
    "LINKEDIN_OAUTH_REVOKE_URL",
    "https://www.linkedin.com/oauth/v2/revoke",
)
LINKEDIN_OAUTH_SCOPES = env(
    "LINKEDIN_OAUTH_SCOPES",
    "openid profile w_member_social",
)
LINKEDIN_OAUTH_TIMEOUT = float(env("LINKEDIN_OAUTH_TIMEOUT", "10"))
OAUTH_STATE_TTL_SECONDS = int(env("OAUTH_STATE_TTL_SECONDS", "600"))
# Scheduled refresh looks this far ahead.  Already-expired rows are included
# too: a valid refresh token can still recover them.
SOCIAL_TOKEN_REFRESH_WINDOW_HOURS = int(
    env("SOCIAL_TOKEN_REFRESH_WINDOW_HOURS", "72")
)
SOCIAL_TOKEN_REFRESH_BATCH_SIZE = int(
    env("SOCIAL_TOKEN_REFRESH_BATCH_SIZE", "200")
)
# Consecutive provider-side refresh failures before a connection is parked in
# ERROR and removed from the Beat selection.
SOCIAL_TOKEN_REFRESH_MAX_FAILURES = int(
    env("SOCIAL_TOKEN_REFRESH_MAX_FAILURES", "3")
)

# ---- Billing ----
# Fail closed: no paid plan may be granted until a checkout + webhook flow is
# wired to a real provider and BILLING_ENABLED is deliberately turned on.
BILLING_ENABLED = env_bool("BILLING_ENABLED", False)
BILLING_PROVIDER = env("BILLING_PROVIDER", "").strip().lower()

# Paddle Billing.  Sandbox and live share the same API shape; only the base
# URL and the keys differ.  Leaving these empty keeps checkout disabled.
PADDLE_API_KEY = env("PADDLE_API_KEY", "")
PADDLE_WEBHOOK_SECRET = env("PADDLE_WEBHOOK_SECRET", "")
PADDLE_API_URL = env("PADDLE_API_URL", "https://api.paddle.com")
PADDLE_ENVIRONMENT = env("PADDLE_ENVIRONMENT", "sandbox")

# ---- Outbound e-mail (transactional: verification, password reset, alerts) ----
# Real SMTP by default.  ``console`` remains available for developers who want
# to read messages in the container logs, but it must never be the production
# value: with the console backend no alert e-mail ever leaves the server.
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "10"))
# Envelope used for error reports to admins (never mixed with transactional mail).
SERVER_EMAIL = env("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

if EMAIL_USE_TLS and EMAIL_USE_SSL:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "EMAIL_USE_TLS and EMAIL_USE_SSL are mutually exclusive — set exactly "
        "one of them (TLS on 587/25, SSL on 465)."
    )
SPECTACULAR_SETTINGS = {
    "TITLE": "Presence API",
    "DESCRIPTION": "API for Presence website health monitoring.",
    "VERSION": "v1",
    "SERVE_INCLUDE_SCHEMA": False,
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploaded files (review CSV imports).  Django's default MEDIA_ROOT is empty,
# which writes next to the working directory and breaks any consumer running in
# another container; pin it under BASE_DIR so the shared media volume works.
MEDIA_URL = env("DJANGO_MEDIA_URL", "/media/")
MEDIA_ROOT = Path(env("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOG_LEVEL = env("DJANGO_LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": JsonFormatter, "format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "filters": {
        "redact_oauth_query": {
            "()": "integrations.logging.OAuthQueryRedactionFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["redact_oauth_query"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
            "filters": ["redact_oauth_query"],
        },
        "celery": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
            "filters": ["redact_oauth_query"],
        },
    },
}

# ---- Extended Celery Beat Schedule ----
CELERY_BEAT_SCHEDULE.update({
    # Crash recovery: both jobs are idempotent and bounded, so a five-minute
    # cadence is cheap.  Their thresholds are configured above.
    "reap-stale-ai-runs": {
        "task": "advisory.tasks.reap_stale_ai_runs",
        "schedule": 300.0,
    },
    "reap-stale-scans": {
        "task": "scans.tasks.reap_stale_scans",
        "schedule": 300.0,
    },
    # Standing credential check: catches a revoked/expired key before a
    # customer scan silently falls back to deterministic recommendations.
    "verify-aka-credentials": {
        "task": "advisory.tasks.verify_aka_credentials",
        "schedule": crontab(hour="*/6", minute=45),
    },
    "sync-reviews-hourly": {
        "task": "reviews.tasks.sync_all_review_sources",
        "schedule": 3600.0,
    },
    "track-mentions-daily": {
        "task": "social.tasks.track_brand_mentions",
        "schedule": 86400.0,
        "args": [],
    },
})

CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", False)
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in env("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
CORS_ALLOW_CREDENTIALS = True

# ---- Scanner Engine configuration ----
# All timeouts in seconds.  Override via SCANNER_TIMEOUT_<NAME> env vars.
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_list(name: str, default: str) -> list[str]:
    """Parse an ordered comma-separated env var, dropping duplicates."""
    raw = env(name, default)
    return list(
        dict.fromkeys(item.strip() for item in raw.split(",") if item.strip())
    )


# ---- AI Growth Advisor (AKA IA) ------------------------------------------
# The key is server-side only.  Empty means the advisor is unavailable and
# ``build_aka_client`` fails closed; no guest-mode fallback is allowed.
AKA_AI_BASE_URL = env("AKA_AI_BASE_URL", "https://ai.elomaiapp.com").rstrip("/")
AKA_AI_API_KEY = env("AKA_AI_API_KEY", "")
AKA_AI_MODELS = _env_list(
    "AKA_AI_MODELS",
    "groq/qwen/qwen3.8-27b,ddgw/gpt-5.4-mini",
)
AKA_AI_MAX_RETRIES = _env_int("AKA_AI_MAX_RETRIES", 2)
AKA_AI_CONNECT_TIMEOUT = _env_float("AKA_AI_CONNECT_TIMEOUT", 3.0)
AKA_AI_READ_TIMEOUT = _env_float("AKA_AI_READ_TIMEOUT", 45.0)
AKA_AI_BACKOFF_BASE = _env_float("AKA_AI_BACKOFF_BASE", 2.0)
AKA_AI_BACKOFF_MAX = _env_float("AKA_AI_BACKOFF_MAX", 60.0)
AKA_AI_MAX_RETRY_AFTER = _env_float("AKA_AI_MAX_RETRY_AFTER", 300.0)
AKA_AI_TEMPERATURE = _env_float("AKA_AI_TEMPERATURE", 0.2)
AKA_AI_MAX_TOKENS = _env_int("AKA_AI_MAX_TOKENS", 900)
AKA_AI_MAX_RESPONSE_BYTES = _env_int("AKA_AI_MAX_RESPONSE_BYTES", 1_000_000)
AKA_AI_USER_AGENT = env("AKA_AI_USER_AGENT", "Presence-AI-Advisor/1.0")
AKA_AI_CIRCUIT_FAILURE_THRESHOLD = _env_int(
    "AKA_AI_CIRCUIT_FAILURE_THRESHOLD", 5
)
AKA_AI_CIRCUIT_RECOVERY_SECONDS = _env_float(
    "AKA_AI_CIRCUIT_RECOVERY_SECONDS", 300.0
)
AI_ADVISOR_ENABLED = env_bool("AI_ADVISOR_ENABLED", False)
AKA_AI_MAX_PROMPT_CHARS = _env_int("AKA_AI_MAX_PROMPT_CHARS", 60_000)
AI_ADVISOR_RETRY_MAX_SECONDS = _env_int("AI_ADVISOR_RETRY_MAX_SECONDS", 900)
# A run whose row has not been touched for this long is considered abandoned
# by a dead worker.  Kept above the 600 s Celery hard limit.
AI_ADVISOR_STALE_RUN_SECONDS = _env_int("AI_ADVISOR_STALE_RUN_SECONDS", 600)
# After the gateway rejects our key, every worker stops calling it for this
# long instead of each scan silently consuming a guest request.
AKA_AI_AUTH_FAILURE_COOLDOWN = _env_int("AKA_AI_AUTH_FAILURE_COOLDOWN", 900)
# Scans have no heartbeat beyond their progress updates; the default is the
# Celery hard limit (600 s) plus a 5-minute margin.  Lower values are floored
# to 300 s in the reaper itself.
SCAN_REAP_RUNNING_AFTER_SECONDS = _env_int(
    "SCAN_REAP_RUNNING_AFTER_SECONDS", 900
)
SCAN_REAP_QUEUED_AFTER_SECONDS = _env_int(
    "SCAN_REAP_QUEUED_AFTER_SECONDS", 900
)


# ---- Advanced security tier (ZAP / Nuclei) --------------------------------
# Off by default: these tools send attack payloads and must never run
# automatically on customer sites.  When false, the orchestrator marks their
# steps as skipped and the adapters refuse to execute even if called directly.
SCANNER_ADVANCED_SECURITY_ENABLED: bool = env_bool(
    "SCANNER_ADVANCED_SECURITY_ENABLED", False
)

# Sandbox image holding the six advanced scanners (nmap, nikto, whatweb,
# testssl.sh, dnsrecon, gobuster).  Built by `docker compose build
# scanner-tools` from docker/scanner-tools/Dockerfile; the tag is pinned here
# so a scheduled scan never runs `latest`.  The sandbox uses
# `--pull never`, so a missing image is reported as an unavailable scanner
# rather than silently pulled during a scan.
SCANNER_TOOLS_IMAGE: Final = env(
    "SCANNER_TOOLS_IMAGE", "presence-scanner-tools:2026-10-27"
).strip() or "presence-scanner-tools:2026-10-27"


def _env_image(name: str, default: str) -> str:
    """Image reference from the environment, falling back when left blank.

    ``.env.example`` (and therefore most deployments) list the image variables
    with an empty value so an operator can override them in place.  An empty
    string must mean "use the project default image", not "this scanner has no
    image": otherwise the six advanced tools would be reported as unavailable
    on a stack where the image is built and present.
    """
    value = os.environ.get(name)
    return (value or "").strip() or default

SCANNER_CONFIG: dict = {
    # Internal Python scanners
    "website":          {"timeout": _env_int("SCANNER_TIMEOUT_WEBSITE", 15)},
    "ssl":              {"timeout": _env_int("SCANNER_TIMEOUT_SSL", 15)},
    "dns":              {"timeout": _env_int("SCANNER_TIMEOUT_DNS", 10)},
    "email_security":   {"timeout": _env_int("SCANNER_TIMEOUT_EMAIL_SECURITY", 15)},
    "security_headers": {"timeout": _env_int("SCANNER_TIMEOUT_SECURITY_HEADERS", 15)},
    "performance":      {"timeout": _env_int("SCANNER_TIMEOUT_PERFORMANCE", 15)},
    "uptime":           {"timeout": _env_int("SCANNER_TIMEOUT_UPTIME", 10)},
    # External CLI tool adapters
    # The six advanced scanners run in the shared `presence-scanner-tools`
    # sandbox image.  Their budgets are deliberately smaller than the previous
    # defaults (nmap 120 / nikto 180 / whatweb 30 / dnsrecon 60 / gobuster 120):
    # a scan runs its steps sequentially inside SCAN_TOTAL_TIME_BUDGET_SECONDS,
    # so every tool must be individually bounded and must be able to close its
    # own report before the sandbox kills the container.  A step whose timeout
    # is reached is reported as such — never as a completed scan.
    "nmap":        {
        "timeout": _env_int("SCANNER_TIMEOUT_NMAP", 75),
        "nse_enabled": env_bool("SCANNER_NMAP_NSE_ENABLED", False),
        "sandbox": {
            "memory_mb": _env_int("SCANNER_NMAP_MEMORY_MB", 256),
            "cpu_seconds": _env_int("SCANNER_NMAP_CPU_SECONDS", 110),
            "pids_limit": _env_int("SCANNER_NMAP_PIDS", 128),
        },
    },
    "nikto":       {
        "timeout": _env_int("SCANNER_TIMEOUT_NIKTO", 100),
        "sandbox": {
            "memory_mb": _env_int("SCANNER_NIKTO_MEMORY_MB", 384),
            "cpu_seconds": _env_int("SCANNER_NIKTO_CPU_SECONDS", 150),
        },
    },
    "nuclei":      {
        # Active profile.  ``standard`` is the only one used by scheduled and
        # manual automatic scans; ``deep`` is opt-in for a dedicated worker
        # because it needs a much larger scan budget.
        "profile": os.environ.get(
            "SCANNER_NUCLEI_PROFILE", "standard"
        ).strip().lower(),
        # Kept for backward compatibility (tests, older deployments).  The
        # selected profile below overrides these values.
        "timeout": _env_int("SCANNER_TIMEOUT_NUCLEI", 150),
        "tags": ["cve", "exposure", "misconfig"],
        # Explicit, bounded profiles.  Measured on a real Cloudflare-fronted
        # target with nuclei v3.11.1 and a 14 104-file template catalogue:
        #   high+critical: 646 templates, 1 300 requests, 83 s (0 errors)
        #   medium+      : 1 066 templates, 3 334 requests, 129–169 s
        #                  (1 958–2 371 request errors under target latency)
        # The medium+ set has too little margin against the 180 s objective,
        # so the automatic ``standard`` profile is high/critical only.  The
        # full exposure/misconfig medium+ set remains available as
        # ``thorough`` and must not be scheduled by default.  ``deep`` adds
        # the full ``cve`` tag selection (including CVEs not tagged
        # exposure/misconfig) and is clamped by
        # SCANNER_SANDBOX["max_timeout"] (300 s by default); it requires a
        # dedicated worker.
        "profiles": {
            "standard": {
                "description": (
                    "Quick exposures/misconfigurations over HTTP, high and "
                    "critical only; no intrusive/default-login/fuzzing "
                    "templates.  150 s hard budget keeps a safety margin "
                    "under the 180 s objective."
                ),
                "tags": ["exposure", "misconfig"],
                "exclude_tags": [
                    "dos",
                    "fuzz",
                    "fuzzing",
                    "intrusive",
                    "brute-force",
                    "default-login",
                    "credential-stuffing",
                    "token-spray",
                ],
                "severity": "critical,high",
                "protocol": "http",
                "ip_version": "4",
                "request_timeout": 5,
                "retries": 1,
                "concurrency": 20,
                "bulk_size": 10,
                "rate_limit": 60,
                "max_host_error": 40,
                # Medium findings are intentionally out of this profile's
                # scope.  A finding outside its coverage must never be
                # resolved just because this narrower scan did not report it.
                "resolve_missing": False,
                "timeout": _env_int("SCANNER_TIMEOUT_NUCLEI_STANDARD", 150),
                # Threshold at which a completed run is considered late.
                # The hard timeout is deliberately equal: a 150 s run is
                # already a partial timeout, never a successful completion.
                "duration_alert_s": 150,
            },
            "thorough": {
                "description": (
                    "Exposure/misconfiguration scan including medium "
                    "severity.  Slower than standard on latency-sensitive "
                    "targets; manual/dedicated use only, never scheduled by "
                    "default."
                ),
                "tags": ["exposure", "misconfig"],
                "exclude_tags": [
                    "dos",
                    "fuzz",
                    "fuzzing",
                    "intrusive",
                    "brute-force",
                    "default-login",
                    "credential-stuffing",
                    "token-spray",
                ],
                "severity": "critical,high,medium",
                "protocol": "http",
                "ip_version": "4",
                "request_timeout": 5,
                "retries": 1,
                # 15/45 measured at 127 s with 1 794 request errors, versus
                # 129–169 s and 1 958–2 371 errors at 20/60.  Lower pressure
                # is both faster on this throttled target and gentler.
                "concurrency": 15,
                "bulk_size": 10,
                "rate_limit": 45,
                "max_host_error": 40,
                # Same coverage limitation as standard, plus medium.
                "resolve_missing": False,
                # Kept below the 180 s absolute limit.  Measured at 127–169 s
                # on the reference target, so a slow run can still end
                # partial; the status makes that explicit.
                "timeout": _env_int("SCANNER_TIMEOUT_NUCLEI_THOROUGH", 178),
                "duration_alert_s": 150,
            },
            "deep": {
                "description": (
                    "Adds the full CVE tag selection, including CVEs not "
                    "already tagged exposure/misconfig.  Requires a dedicated "
                    "worker and a scan budget above the 540 s default; never "
                    "scheduled by default."
                ),
                "tags": ["cve", "exposure", "misconfig"],
                "exclude_tags": [
                    "dos",
                    "fuzz",
                    "fuzzing",
                    "intrusive",
                    "brute-force",
                    "default-login",
                    "credential-stuffing",
                    "token-spray",
                ],
                "severity": "critical,high,medium",
                "protocol": "http",
                "ip_version": "4",
                "request_timeout": 8,
                "retries": 1,
                "concurrency": 15,
                "bulk_size": 10,
                "rate_limit": 50,
                "max_host_error": 45,
                # Still narrower than the whole catalog (info/low templates
                # and intrusive families are excluded); do not auto-resolve.
                "resolve_missing": False,
                # Effective cap is SCANNER_SANDBOX["max_timeout"] (300 s by
                # default); raise both deliberately on a dedicated worker
                # before treating deep as operational.
                "timeout": _env_int("SCANNER_TIMEOUT_NUCLEI_DEEP", 540),
                "duration_alert_s": 540,
            },
        },
        # Host path containing the template repository.  In Docker mode it
        # is bind-mounted read-only at /nuclei-templates; the official Nuclei
        # image ships the binary only, not the templates.
        "templates_path": os.environ.get(
            "SCANNER_NUCLEI_TEMPLATES_PATH", ""
        ).strip(),
        # Deployment-reported versions stored in archive metadata.  Empty is
        # honest (``unknown``) rather than a guessed or stale value.
        "binary_version": os.environ.get(
            "SCANNER_NUCLEI_BINARY_VERSION", ""
        ).strip(),
        "templates_version": os.environ.get(
            "SCANNER_NUCLEI_TEMPLATES_VERSION", ""
        ).strip(),
        # 14k+ bundled templates are loaded into RAM; 512 MB is OOM-killed
        # before the first request (exit 137) on the official image.
        "sandbox": {
            "memory_mb": _env_int("SCANNER_NUCLEI_MEMORY_MB", 1536),
        },
    },
    "whatweb":     {
        "timeout": _env_int("SCANNER_TIMEOUT_WHATWEB", 25),
        "sandbox": {
            "memory_mb": _env_int("SCANNER_WHATWEB_MEMORY_MB", 384),
            "cpu_seconds": _env_int("SCANNER_WHATWEB_CPU_SECONDS", 45),
        },
    },
    "testssl":     {
        # Measured on a real Cloudflare-fronted target with testssl 3.0.8:
        # the bounded standard set (``--std``: protocols, standard cipher
        # categories, server defaults/certificate, HSTS/security headers)
        # completes in ~50 s.  A full run, and even ``--fast``, still exceeds
        # 200 s there and can never finish inside a per-step budget, so the
        # step deliberately runs the standard set instead of inflating the
        # timeout.  Vulnerability probes (``-U``) and per-cipher enumeration
        # are therefore not part of this step.
        "timeout": _env_int("SCANNER_TIMEOUT_TESTSSL", 90),
        # Debian's testssl.sh package installs /usr/bin/testssl.
        "binary": os.environ.get("SCANNER_TESTSSL_BINARY", "testssl"),
        # Verified in the pinned upstream script: a completed run exits
        # `$ALLOK` (declared 0) whatever the severities reported; 244-255 are
        # fatal/abort codes.  A non-zero exit therefore means no full coverage.
        "ok_exit_codes": [0],
        "sandbox": {
            "memory_mb": _env_int("SCANNER_TESTSSL_MEMORY_MB", 384),
            "cpu_seconds": _env_int("SCANNER_TESTSSL_CPU_SECONDS", 120),
        },
    },
    # Lighthouse runs Chromium: it needs more RSS than the default tool and
    # is the canonical example of an external tool delegated by the engine.
    "lighthouse": {
        "timeout": _env_int("SCANNER_TIMEOUT_LIGHTHOUSE", 120),
        "binary": os.environ.get("SCANNER_LIGHTHOUSE_BINARY", "lighthouse"),
        "categories": [
            item.strip()
            for item in os.environ.get(
                "SCANNER_LIGHTHOUSE_CATEGORIES", "performance,seo"
            ).split(",")
            if item.strip()
        ],
        "preset": os.environ.get("SCANNER_LIGHTHOUSE_PRESET", "desktop"),
        "chrome_flags": os.environ.get(
            "SCANNER_LIGHTHOUSE_CHROME_FLAGS",
            "--headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu",
        ),
        "chrome_proxy": os.environ.get("SCANNER_LIGHTHOUSE_CHROME_PROXY", ""),
        "chrome_path": os.environ.get("CHROME_PATH", ""),
        "pin_target_ip": env_bool("SCANNER_LIGHTHOUSE_PIN_TARGET_IP", True),
        "min_score": _env_int("SCANNER_LIGHTHOUSE_MIN_SCORE", 90),
        "max_findings": _env_int("SCANNER_LIGHTHOUSE_MAX_FINDINGS", 60),
        "sandbox": {
            "memory_mb": _env_int("SCANNER_LIGHTHOUSE_MEMORY_MB", 2048),
            "cpu_seconds": _env_int("SCANNER_LIGHTHOUSE_CPU_SECONDS", 180),
            "file_size_mb": _env_int("SCANNER_LIGHTHOUSE_FILE_SIZE_MB", 64),
            # Chromium opens many descriptors; the global default (1024) is
            # enough for other CLI tools but too tight for a headless browser.
            "open_files": _env_int("SCANNER_LIGHTHOUSE_OPEN_FILES", 4096),
        },
    },
    "dnsrecon":    {
        "timeout": _env_int("SCANNER_TIMEOUT_DNSRECON", 30),
        # Per-query budget for the standard enumeration (NS/SOA/A/AAAA/MX/SRV).
        "lifetime_seconds": _env_int("SCANNER_DNSRECON_LIFETIME_SECONDS", 8),
        "sandbox": {
            "memory_mb": _env_int("SCANNER_DNSRECON_MEMORY_MB", 256),
            "cpu_seconds": _env_int("SCANNER_DNSRECON_CPU_SECONDS", 45),
        },
    },
    "gobuster":    {
        "timeout": _env_int("SCANNER_TIMEOUT_GOBUSTER", 45),
        # Debian's dirb package ships the wordlist; it is versioned with the
        # sandbox image and never supplied by scan input.
        "wordlist": os.environ.get(
            "SCANNER_GOBUSTER_WORDLIST", "/usr/share/dirb/wordlists/common.txt"
        ),
        "threads": _env_int("SCANNER_GOBUSTER_THREADS", 10),
        "request_timeout": os.environ.get(
            "SCANNER_GOBUSTER_REQUEST_TIMEOUT", "10s"
        ),
        "sandbox": {
            "memory_mb": _env_int("SCANNER_GOBUSTER_MEMORY_MB", 256),
            "cpu_seconds": _env_int("SCANNER_GOBUSTER_CPU_SECONDS", 70),
        },
    },
    "feroxbuster": {
        "timeout": _env_int("SCANNER_TIMEOUT_FEROXBUSTER", 120),
        "wordlist": os.environ.get("SCANNER_FEROXBUSTER_WORDLIST", "/usr/share/wordlists/dirb/common.txt"),
        "threads": _env_int("SCANNER_FEROXBUSTER_THREADS", 10),
    },
    "zap":         {
        "timeout": _env_int("SCANNER_TIMEOUT_ZAP", 300),
        # "auto" prefers the sandboxed Docker image when Docker mode and an
        # image are configured, and falls back to the REST sidecar otherwise.
        "mode": os.environ.get("SCANNER_ZAP_MODE", "auto").strip().lower(),
        "api_url": os.environ.get("ZAP_API_URL", "http://zap-scanner:8090"),
        "api_key": os.environ.get("ZAP_API_KEY", ""),
        "docker_image": os.environ.get("SCANNER_DOCKER_IMAGE_ZAP", "").strip(),
        # Script executed inside the image; the sandbox clears the image
        # entrypoint so every ZAP tag behaves identically.
        "script": os.environ.get("SCANNER_ZAP_SCRIPT", "zap-baseline.py").strip(),
        # Active scanning is intrusive; the passive baseline is the default.
        "active_scan": env_bool("SCANNER_ZAP_ACTIVE_SCAN", False),
        "sandbox": {
            "memory_mb": _env_int("SCANNER_ZAP_MEMORY_MB", 1536),
            "cpu_seconds": _env_int("SCANNER_ZAP_CPU_SECONDS", 360),
            "tmpfs": ["/zap/wrk:rw,nosuid,nodev,size=64m"],
        },
    },
}

# ---- Scanner sandbox (external tool delegation) ---------------------------
# ``mode``: "process" (child process with rlimits + RSS watchdog) or "docker"
# (one-shot hardened container with cgroup limits).
SCANNER_SANDBOX: dict = {
    "mode": env("SCANNER_SANDBOX_MODE", "process").strip().lower(),
    "default_timeout": _env_int("SCANNER_SANDBOX_DEFAULT_TIMEOUT", 60),
    "max_timeout": _env_int("SCANNER_SANDBOX_MAX_TIMEOUT", 300),
    "default_memory_mb": _env_int("SCANNER_SANDBOX_DEFAULT_MEMORY_MB", 512),
    "default_file_size_mb": _env_int("SCANNER_SANDBOX_DEFAULT_FILE_SIZE_MB", 64),
    "default_open_files": _env_int("SCANNER_SANDBOX_DEFAULT_OPEN_FILES", 1024),
    "max_output_bytes": _env_int(
        "SCANNER_SANDBOX_MAX_OUTPUT_BYTES", 5 * 1024 * 1024
    ),
    # Cross-worker semaphore stored in Redis. 0 disables the gate.
    "max_concurrency": _env_int("SCANNER_SANDBOX_MAX_CONCURRENCY", 2),
    # Directory the worker and the Docker daemon both see, used for the files
    # a scanner must write (ZAP needs a bind mount for ``/zap/wrk``).  In the
    # containerised stack it is a host bind mount; empty keeps ``/tmp``, which
    # is only valid when the worker runs directly on the Docker host.
    "shared_work_dir": env("SCANNER_SANDBOX_SHARED_WORK_DIR", "").strip(),
    "docker": {
        "binary": env("SCANNER_SANDBOX_DOCKER_BINARY", "docker"),
        "network": env("SCANNER_SANDBOX_DOCKER_NETWORK", "bridge"),
        "cpus": _env_float("SCANNER_SANDBOX_DOCKER_CPUS", 1.0),
        "pids_limit": _env_int("SCANNER_SANDBOX_DOCKER_PIDS", 256),
        "shm_size_mb": _env_int("SCANNER_SANDBOX_DOCKER_SHM_MB", 256),
        "user": env("SCANNER_SANDBOX_DOCKER_USER", ""),
        # Never pull at scan time: the image must be pre-pulled on the VPS.
        "pull_policy": env("SCANNER_SANDBOX_DOCKER_PULL", "never"),
        "start_grace_seconds": _env_int(
            "SCANNER_SANDBOX_DOCKER_START_GRACE", 20
        ),
        "images": {
            # Lighthouse/Chromium and ZAP keep their own images: the first is
            # optional (see steps_builder) and the second is a 2 GB vendor
            # image.  The six advanced tools share one project image, built by
            # `docker compose build scanner-tools`.
            "lighthouse": env("SCANNER_DOCKER_IMAGE_LIGHTHOUSE", ""),
            "testssl": _env_image("SCANNER_DOCKER_IMAGE_TESTSSL", SCANNER_TOOLS_IMAGE),
            "nmap": _env_image("SCANNER_DOCKER_IMAGE_NMAP", SCANNER_TOOLS_IMAGE),
            "nikto": _env_image("SCANNER_DOCKER_IMAGE_NIKTO", SCANNER_TOOLS_IMAGE),
            "whatweb": _env_image("SCANNER_DOCKER_IMAGE_WHATWEB", SCANNER_TOOLS_IMAGE),
            "dnsrecon": _env_image("SCANNER_DOCKER_IMAGE_DNSRECON", SCANNER_TOOLS_IMAGE),
            "gobuster": _env_image("SCANNER_DOCKER_IMAGE_GOBUSTER", SCANNER_TOOLS_IMAGE),
            "nuclei": env("SCANNER_DOCKER_IMAGE_NUCLEI", ""),
            "zap": env("SCANNER_DOCKER_IMAGE_ZAP", ""),
        },
    },
}

# Hard wall-clock budget for a whole scan, shared by all steps.
SCAN_TOTAL_TIME_BUDGET_SECONDS: int = _env_int(
    "SCAN_TOTAL_TIME_BUDGET_SECONDS", 540
)

# Maximum concurrent authenticated scans per user.
MAX_CONCURRENT_SCANS_PER_USER: int = _env_int("MAX_CONCURRENT_SCANS_PER_USER", 1)

# ---- External data providers (all optional; scanners degrade honestly) ----
# Google Safe Browsing malware reputation (https://developers.google.com/safe-browsing)
GOOGLE_SAFE_BROWSING_API_KEY = env("GOOGLE_SAFE_BROWSING_API_KEY", "")
# Meta Graph API (Facebook Pages / Instagram Business) follower sync
META_GRAPH_ACCESS_TOKEN = env("META_GRAPH_ACCESS_TOKEN", "")
# X/Twitter API v2 bearer token for follower sync
X_BEARER_TOKEN = env("X_BEARER_TOKEN", "")
# Reddit requires a descriptive User-Agent for its public JSON API
REDDIT_USER_AGENT = env(
    "REDDIT_USER_AGENT", "Presence-Monitor/1.0 (+https://presence.local)"
)

# Maximum raw scanner output size stored in DB (characters).
SCANNER_MAX_RAW_OUTPUT: int = _env_int("SCANNER_MAX_RAW_OUTPUT", 50_000)

# Maximum subprocess output before truncation (bytes).
SCANNER_MAX_SUBPROCESS_OUTPUT: int = _env_int("SCANNER_MAX_SUBPROCESS_OUTPUT", 10 * 1024 * 1024)

# ---- Raw scanner report archives -----------------------------------------
# Private copy of the raw JSONL, including partial output from a timeout.
# It is redacted before writing and stored outside MEDIA_ROOT, in a dedicated
# volume with 0700/0600 permissions.  Archiving is best-effort: its failure is
# recorded in ScannerRun.metadata and never fails a scan or suppresses
# ingestion.
SCANNER_ARCHIVE_ENABLED: bool = env_bool("SCANNER_ARCHIVE_ENABLED", True)
# Nuclei plus the six advanced tools: their reports are small text/JSON
# artefacts, their findings are what a completed security scan is audited
# against, and an incomplete run must stay diagnosable from its raw output.
SCANNER_ARCHIVE_SCANNERS: tuple[str, ...] = (
    "nuclei",
    "nmap",
    "nikto",
    "whatweb",
    "testssl",
    "dnsrecon",
    "gobuster",
)
SCANNER_ARCHIVE_DIR: str = env(
    "SCANNER_ARCHIVE_DIR", str(BASE_DIR / "scanner-archives")
)
SCANNER_ARCHIVE_MAX_BYTES: int = _env_int(
    "SCANNER_ARCHIVE_MAX_BYTES", 8 * 1024 * 1024
)
SCANNER_ARCHIVE_RETENTION_DAYS: int = _env_int(
    "SCANNER_ARCHIVE_RETENTION_DAYS", 30
)


# === PHASE2_RATE_LIMIT_I18N_PATCH ===
# 🆕 Phase 2 (Sept 2026) — Rate-limiting public scan 5/h + support i18n emails
REST_FRAMEWORK.setdefault("DEFAULT_THROTTLE_CLASSES", [
    "rest_framework.throttling.AnonRateThrottle",
    "rest_framework.throttling.UserRateThrottle",
])
REST_FRAMEWORK.setdefault("DEFAULT_THROTTLE_RATES", {})
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["public_scan"] = "5/hour"
REST_FRAMEWORK["NUM_PROXIES"] = 1  # Nginx reverse-proxy → vraie IP via X-Forwarded-For

LANGUAGES = [
    ("fr", "Français"),
    ("en", "English"),
    ("de", "Deutsch"),
]
USE_I18N = True
# === END PHASE2_RATE_LIMIT_I18N_PATCH ===
