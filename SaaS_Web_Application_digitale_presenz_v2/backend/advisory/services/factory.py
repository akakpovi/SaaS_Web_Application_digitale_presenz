"""Build the AKA IA client from Django settings.

``aka_client.py`` stays Django-free; this module is the only place that reads
``django.conf.settings``.  Callers that need an override (tests, Celery
workers) can inject a session, sleep callable or circuit breaker.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .aka_client import AkaAIClient, AkaConfig


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
        dict.fromkeys(
            str(model).strip() for model in raw_models if str(model).strip()
        )
    )
    if not models:
        raise ImproperlyConfigured(
            "AKA_AI_MODELS must contain at least one model."
        )

    config = AkaConfig(
        api_key=api_key,
        base_url=getattr(
            settings, "AKA_AI_BASE_URL", "https://ai.elomaiapp.com"
        ),
        models=models,
        max_retries=getattr(settings, "AKA_AI_MAX_RETRIES", 2),
        connect_timeout=getattr(settings, "AKA_AI_CONNECT_TIMEOUT", 3.0),
        read_timeout=getattr(settings, "AKA_AI_READ_TIMEOUT", 45.0),
        backoff_base=getattr(settings, "AKA_AI_BACKOFF_BASE", 2.0),
        backoff_max=getattr(settings, "AKA_AI_BACKOFF_MAX", 60.0),
        max_retry_after=getattr(settings, "AKA_AI_MAX_RETRY_AFTER", 300.0),
        temperature=getattr(settings, "AKA_AI_TEMPERATURE", 0.2),
        max_tokens=getattr(settings, "AKA_AI_MAX_TOKENS", 900),
        max_response_bytes=getattr(
            settings, "AKA_AI_MAX_RESPONSE_BYTES", 1_000_000
        ),
        user_agent=getattr(
            settings, "AKA_AI_USER_AGENT", "Presence-AI-Advisor/1.0"
        ),
        circuit_failure_threshold=getattr(
            settings, "AKA_AI_CIRCUIT_FAILURE_THRESHOLD", 5
        ),
        circuit_recovery_seconds=getattr(
            settings, "AKA_AI_CIRCUIT_RECOVERY_SECONDS", 300.0
        ),
    )
    return AkaAIClient(config, **client_kwargs)
