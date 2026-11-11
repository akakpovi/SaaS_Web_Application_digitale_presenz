"""Build the AKA IA client from Django settings.

``aka_client.py`` stays Django-free; this module is the only place that reads
``django.conf.settings``.  Callers that need an override (tests, Celery
workers) can inject a session, sleep callable or circuit breaker.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured

from .aka_client import AkaAIClient, AkaConfig

logger = logging.getLogger(__name__)

#: Shared marker so every worker stops calling a gateway that rejected the
#: key.  Without it each new scan would consume one guest request, and the
#: pipeline would only notice at the 429.
CREDENTIALS_INVALID_CACHE_KEY = "advisory:aka_credentials_invalid"


def _credentials_cooldown_seconds() -> int:
    try:
        return max(60, int(getattr(settings, "AKA_AI_AUTH_FAILURE_COOLDOWN", 900)))
    except (TypeError, ValueError):
        return 900


def mark_aka_credentials_invalid(reason: str = "invalid_api_key") -> None:
    """Remember that the gateway rejected the configured key.

    Cache failures must never break the advisor: they are logged and the
    call proceeds, because a cold cache only costs one extra probe.
    """
    try:
        cache.set(
            CREDENTIALS_INVALID_CACHE_KEY,
            {"reason": (reason or "invalid_api_key")[:200]},
            timeout=_credentials_cooldown_seconds(),
        )
    except Exception:
        logger.warning("aka_ai_credentials_cache_unavailable")


def aka_credentials_marked_invalid() -> dict | None:
    try:
        value = cache.get(CREDENTIALS_INVALID_CACHE_KEY)
    except Exception:
        logger.warning("aka_ai_credentials_cache_unavailable")
        return None
    return value if isinstance(value, dict) else None


def clear_aka_credentials_invalid() -> None:
    try:
        cache.delete(CREDENTIALS_INVALID_CACHE_KEY)
    except Exception:
        logger.warning("aka_ai_credentials_cache_unavailable")


def build_aka_client(**client_kwargs: Any) -> AkaAIClient:
    """Return a configured client, or fail closed when the key is missing."""
    api_key = (getattr(settings, "AKA_AI_API_KEY", "") or "").strip()
    if not api_key:
        raise ImproperlyConfigured(
            "AKA_AI_API_KEY is not configured; the AI advisor is unavailable."
        )

    raw_models = getattr(settings, "AKA_AI_MODELS", ()) or ()
    if isinstance(raw_models, str):
        raw_models = raw_models.split(",")
    models = tuple(
        dict.fromkeys(str(model).strip() for model in raw_models if str(model).strip())
    )
    if not models:
        raise ImproperlyConfigured("AKA_AI_MODELS must contain at least one model.")

    config = AkaConfig(
        api_key=api_key,
        base_url=getattr(settings, "AKA_AI_BASE_URL", "https://ai.elomaiapp.com"),
        models=models,
        max_retries=getattr(settings, "AKA_AI_MAX_RETRIES", 2),
        connect_timeout=getattr(settings, "AKA_AI_CONNECT_TIMEOUT", 3.0),
        read_timeout=getattr(settings, "AKA_AI_READ_TIMEOUT", 45.0),
        backoff_base=getattr(settings, "AKA_AI_BACKOFF_BASE", 2.0),
        backoff_max=getattr(settings, "AKA_AI_BACKOFF_MAX", 60.0),
        max_retry_after=getattr(settings, "AKA_AI_MAX_RETRY_AFTER", 300.0),
        temperature=getattr(settings, "AKA_AI_TEMPERATURE", 0.2),
        max_tokens=getattr(settings, "AKA_AI_MAX_TOKENS", 900),
        max_response_bytes=getattr(settings, "AKA_AI_MAX_RESPONSE_BYTES", 1_000_000),
        user_agent=getattr(settings, "AKA_AI_USER_AGENT", "Presence-AI-Advisor/1.0"),
        circuit_failure_threshold=getattr(
            settings, "AKA_AI_CIRCUIT_FAILURE_THRESHOLD", 5
        ),
        circuit_recovery_seconds=getattr(
            settings, "AKA_AI_CIRCUIT_RECOVERY_SECONDS", 300.0
        ),
    )
    return AkaAIClient(config, **client_kwargs)
