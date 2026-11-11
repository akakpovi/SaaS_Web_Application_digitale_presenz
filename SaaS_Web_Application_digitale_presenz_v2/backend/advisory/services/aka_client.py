"""HTTP client for the AKA IA ``/v1/chat/completions`` gateway.

The module deliberately has **no Django import**.  All configuration is
injected through :class:`AkaConfig`, so the client can be reused by Celery
workers, management commands or unit tests without bootstrapping Django.

Security invariants
-------------------
* The API key is never logged, never placed in a URL and never included in a
  ``repr``.
* Prompts and raw provider responses are never logged.
* Only the fixed HTTPS base URL is called; redirects are not followed.
* Responses are read with a hard size limit.
* Configuration errors (400/401/403/404/405/422) are never retried.
* Transient errors (408/425/429/5xx/timeouts/connection errors) are retried
  with exponential backoff and jitter; ``Retry-After`` is honoured.
* A long ``Retry-After`` (e.g. the gateway's guest quota of 86 400 s) is
  surfaced immediately instead of blocking a worker for a day.
"""

from __future__ import annotations

import json
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

_ALLOWED_ROLES = frozenset({"system", "user", "assistant"})
_CONFIG_ERROR_STATUSES = frozenset({400, 401, 403, 404, 405, 422})
_TRANSIENT_HTTP_STATUSES = frozenset({408, 425})
DEFAULT_MODEL = "groq/qwen/qwen3.8-27b"
DEFAULT_MODELS = (DEFAULT_MODEL,)


@dataclass(frozen=True)
class AkaConfig:
    """Configuration for :class:`AkaAIClient`.

    ``api_key`` is excluded from ``repr`` so a stray log of the config cannot
    leak the credential.
    """

    api_key: str = field(repr=False)
    base_url: str = "https://ai.elomaiapp.com"
    models: tuple[str, ...] = DEFAULT_MODELS
    max_retries: int = 2
    connect_timeout: float = 3.0
    read_timeout: float = 45.0
    backoff_base: float = 2.0
    backoff_max: float = 60.0
    max_retry_after: float = 300.0
    temperature: float = 0.2
    max_tokens: int = 900
    max_response_bytes: int = 1_000_000
    user_agent: str = "Presence-AI-Advisor/1.0"
    # The gateway serves anonymous callers through a small daily guest quota
    # and advertises that policy with this header.  Authenticated responses
    # carry no ``x-ratelimit-*`` header at all (measured 2026-10-28).  A
    # present header therefore means the supplied key was not honoured.
    guest_mode_header: str = "x-ratelimit-limit"
    circuit_failure_threshold: int = 5
    circuit_recovery_seconds: float = 300.0
    circuit_half_open_max_calls: int = 1

    def __post_init__(self) -> None:
        key = (self.api_key or "").strip()
        if key.lower().startswith("bearer "):
            key = key[7:].strip()
        if not key:
            raise ValueError("AKA_AI_API_KEY is required")
        object.__setattr__(self, "api_key", key)

        base_url = (self.base_url or "").strip().rstrip("/")
        parsed = urlparse(base_url)
        is_loopback_http = parsed.scheme == "http" and parsed.hostname in {
            "localhost",
            "127.0.0.1",
            "::1",
        }
        if parsed.scheme != "https" and not is_loopback_http:
            raise ValueError("AKA_AI_BASE_URL must use https://")
        if not parsed.netloc:
            raise ValueError("AKA_AI_BASE_URL must be an absolute URL")
        object.__setattr__(self, "base_url", base_url)

        raw_models = self.models or ()
        if isinstance(raw_models, str):
            raw_models = raw_models.split(",")
        normalized_models = tuple(
            dict.fromkeys(item.strip() for item in raw_models if item and item.strip())
        )
        if not normalized_models:
            raise ValueError("AKA_AI_MODELS must contain at least one model")
        object.__setattr__(self, "models", normalized_models)

        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.connect_timeout <= 0 or self.read_timeout <= 0:
            raise ValueError("timeouts must be > 0")
        if self.backoff_base < 0 or self.backoff_max < 0:
            raise ValueError("backoff values must be >= 0")
        if self.max_retry_after < 0:
            raise ValueError("max_retry_after must be >= 0")
        if not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if self.max_response_bytes < 1:
            raise ValueError("max_response_bytes must be >= 1")
        if not (self.user_agent or "").strip():
            raise ValueError("user_agent is required")
        if not (self.guest_mode_header or "").strip():
            raise ValueError("guest_mode_header is required")
        if self.circuit_failure_threshold < 1:
            raise ValueError("circuit_failure_threshold must be >= 1")
        if self.circuit_recovery_seconds <= 0:
            raise ValueError("circuit_recovery_seconds must be > 0")
        if self.circuit_half_open_max_calls < 1:
            raise ValueError("circuit_half_open_max_calls must be >= 1")


@dataclass(frozen=True)
class AkaCompletion:
    """Normalised subset of an OpenAI-compatible chat completion."""

    id: str
    model: str
    content: str
    finish_reason: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    request_id: str | None = None
    system_fingerprint: str | None = None
    latency_ms: int = 0


class AkaError(Exception):
    """Base error for every AKA IA failure."""

    retryable = False

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str = "",
        request_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        self.retry_after = retry_after


class AkaConfigurationError(AkaError):
    """The request or the integration is misconfigured; never retry."""


class AkaAuthenticationError(AkaConfigurationError):
    """The gateway answered as an anonymous guest, not as our account.

    This is a configuration failure, not a provider outage: the configured
    ``AKA_AI_API_KEY`` was absent, expired or rejected.  It must never be
    retried and must never be reported as a quota problem, otherwise the
    pipeline silently burns the 3-request guest quota and then sees a 429.
    """


class AkaRateLimitError(AkaError):
    """The provider rate-limited us; retryable only when Retry-After is short."""

    retryable = True


class AkaServerError(AkaError):
    """A transient provider-side failure (5xx/408/425)."""

    retryable = True


class AkaTimeoutError(AkaError):
    """The HTTP call timed out."""

    retryable = True


class AkaConnectionError(AkaError):
    """The provider could not be reached."""

    retryable = True


class AkaInvalidResponseError(AkaError):
    """The provider returned a body that is not a valid chat completion."""


class AkaCircuitOpenError(AkaError):
    """The local circuit breaker refused to send the request."""

    def __init__(self, retry_after: float) -> None:
        super().__init__(
            f"AKA AI circuit breaker is open; retry in {retry_after:.0f}s",
            retry_after=retry_after,
        )


class InMemoryCircuitBreaker:
    """Thread-safe in-process circuit breaker.

    Production should replace this with a Redis-backed implementation so all
    Celery workers share the same state.  The client only relies on the
    ``before_request`` / ``record_success`` / ``record_failure`` contract.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_seconds: float = 300.0,
        half_open_max_calls: int = 1,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if recovery_seconds <= 0:
            raise ValueError("recovery_seconds must be > 0")
        if half_open_max_calls < 1:
            raise ValueError("half_open_max_calls must be >= 1")
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.half_open_max_calls = half_open_max_calls
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._state = "closed"
        self._failures = 0
        self._half_open_calls = 0
        self._open_until = 0.0

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failures

    def before_request(self) -> None:
        with self._lock:
            now = self._clock()
            if self._state == "open":
                if now < self._open_until:
                    raise AkaCircuitOpenError(max(0.0, self._open_until - now))
                self._state = "half_open"
                self._half_open_calls = 0
            if self._state == "half_open":
                if self._half_open_calls >= self.half_open_max_calls:
                    raise AkaCircuitOpenError(max(0.0, self._open_until - now))
                self._half_open_calls += 1

    def record_success(self) -> None:
        with self._lock:
            self._state = "closed"
            self._failures = 0
            self._half_open_calls = 0
            self._open_until = 0.0

    def record_failure(self) -> None:
        with self._lock:
            if self._state == "half_open":
                self._open()
                return
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._open()

    def _open(self) -> None:
        self._state = "open"
        self._open_until = self._clock() + self.recovery_seconds
        self._half_open_calls = 0
        logger.warning(
            "aka_ai_circuit_opened failures=%d recovery_s=%.0f",
            self._failures,
            self.recovery_seconds,
        )


class AkaAIClient:
    """Small, dependency-injectable client for AKA IA chat completions."""

    def __init__(
        self,
        config: AkaConfig,
        *,
        session: Any | None = None,
        circuit_breaker: InMemoryCircuitBreaker | None = None,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
        random_fn: Callable[[], float] | None = None,
    ) -> None:
        self.config = config
        owns_session = session is None
        if owns_session:
            # Retries are implemented below; urllib3 must not add its own.
            session = requests.Session()
            adapter = HTTPAdapter(max_retries=0)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
        self._session = session
        self._owns_session = owns_session
        self._sleep = sleep or time.sleep
        self._clock = clock or time.monotonic
        self._random = random_fn or random.random
        self._circuit = circuit_breaker or InMemoryCircuitBreaker(
            failure_threshold=config.circuit_failure_threshold,
            recovery_seconds=config.circuit_recovery_seconds,
            half_open_max_calls=config.circuit_half_open_max_calls,
            clock=self._clock,
        )

    def __repr__(self) -> str:
        return (
            f"<AkaAIClient base_url={self.config.base_url!r} "
            f"models={self.config.models!r}>"
        )

    def __enter__(self) -> "AkaAIClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_session:
            close = getattr(self._session, "close", None)
            if callable(close):
                close()

    def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AkaCompletion:
        """Send a non-streaming chat completion request.

        ``messages`` must be a non-empty sequence of ``{"role", "content"}``
        mappings.  The client does not accept tool calls or function schemas
        in Phase 1.
        """
        self._validate_messages(messages)
        resolved_model = model or self.config.models[0]
        if resolved_model not in self.config.models:
            raise ValueError("model must be one of AKA_AI_MODELS")
        resolved_temperature = (
            self.config.temperature if temperature is None else temperature
        )
        resolved_max_tokens = (
            self.config.max_tokens if max_tokens is None else max_tokens
        )
        if not 0 <= resolved_temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if resolved_max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")

        payload = {
            "model": resolved_model,
            "messages": list(messages),
            "temperature": resolved_temperature,
            "max_tokens": resolved_max_tokens,
            "stream": False,
        }
        url = f"{self.config.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.config.user_agent,
        }

        for attempt in range(self.config.max_retries + 1):
            self._circuit.before_request()
            started = self._clock()

            try:
                status_code, response_headers, body = self._post(url, payload, headers)
            except requests.Timeout:
                error: AkaError = AkaTimeoutError("AKA AI request timed out")
                if not self._can_retry(attempt):
                    self._circuit.record_failure()
                    raise error
                self._wait_before_retry(attempt, error)
                continue
            except requests.RequestException as exc:
                error = AkaConnectionError(
                    f"AKA AI connection error ({exc.__class__.__name__})"
                )
                if not self._can_retry(attempt):
                    self._circuit.record_failure()
                    raise error
                self._wait_before_retry(attempt, error)
                continue
            except AkaInvalidResponseError:
                self._circuit.record_failure()
                raise

            if status_code == 200:
                try:
                    completion = self._parse_completion(body, response_headers, started)
                except AkaInvalidResponseError:
                    self._circuit.record_failure()
                    raise
                # A 200 served in guest mode is not an authenticated success.
                if self._guest_limit(response_headers) is not None:
                    self._reject_guest_response(
                        status_code,
                        response_headers,
                        request_id=completion.request_id,
                    )
                self._circuit.record_success()
                return completion

            error = self._error_from_response(status_code, response_headers, body)
            if self._is_guest_response(response_headers, error):
                self._reject_guest_response(
                    status_code,
                    response_headers,
                    request_id=error.request_id,
                    detail=error.code,
                )
            if not error.retryable or not self._can_retry(attempt):
                self._circuit.record_failure()
                raise error
            if (
                error.retry_after is not None
                and error.retry_after > self.config.max_retry_after
            ):
                # A 24-hour guest quota must never park a Celery worker.
                self._circuit.record_failure()
                raise error
            self._wait_before_retry(attempt, error)

        # The loop always raises on the last attempt; this is defensive.
        raise AkaError("AKA AI request failed")

    # ------------------------------------------------------------------
    # Credential validation
    # ------------------------------------------------------------------

    def _guest_limit(self, headers: Mapping[str, Any]) -> str | None:
        raw = self._get_header(headers, self.config.guest_mode_header)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("ascii", "ignore")
        return str(raw).strip() or "unknown"

    def _is_guest_response(self, headers: Mapping[str, Any], error: AkaError) -> bool:
        if self._guest_limit(headers) is not None:
            return True
        return (error.code or "").lower() == "guest_quota_exceeded"

    def _reject_guest_response(
        self,
        status_code: int,
        headers: Mapping[str, Any],
        *,
        request_id: str | None = None,
        detail: str = "",
    ) -> None:
        """Fail loudly instead of consuming the anonymous quota.

        Never include the API key or the response body in the log line: the
        guest limit and HTTP status are enough to diagnose the deployment.
        """
        limit = self._guest_limit(headers)
        logger.error(
            "aka_ai_invalid_credentials status=%s guest_limit=%s detail=%s",
            status_code,
            limit or "missing-header",
            detail or "-",
        )
        raise AkaAuthenticationError(
            "AKA AI served the request in guest mode: the configured "
            "AKA_AI_API_KEY is missing, expired or rejected by the gateway",
            status_code=status_code,
            code="invalid_api_key",
            request_id=request_id,
        )

    # ------------------------------------------------------------------
    # Retry helpers
    # ------------------------------------------------------------------

    def _can_retry(self, attempt: int) -> bool:
        return attempt < self.config.max_retries

    def _wait_before_retry(self, attempt: int, error: AkaError) -> None:
        delay = self._retry_delay(attempt, error.retry_after)
        logger.warning(
            "aka_ai_retry status=%s code=%s attempt=%d delay_s=%.2f",
            error.status_code,
            error.code or "-",
            attempt + 1,
            delay,
        )
        self._sleep(delay)

    def _retry_delay(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return max(0.0, retry_after)
        base = min(
            self.config.backoff_max,
            self.config.backoff_base * (2**attempt),
        )
        jitter = self._random() * min(1.0, max(0.0, base * 0.25))
        return max(0.0, base + jitter)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _post(
        self,
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
    ) -> tuple[int, dict[str, Any], bytes]:
        response = self._session.post(
            url,
            json=payload,
            headers=dict(headers),
            timeout=(self.config.connect_timeout, self.config.read_timeout),
            allow_redirects=False,
            stream=True,
        )
        try:
            status_code = int(getattr(response, "status_code", 0) or 0)
            response_headers = dict(getattr(response, "headers", {}) or {})
            body = self._read_body(response)
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
        return status_code, response_headers, body

    def _read_body(self, response: Any) -> bytes:
        limit = self.config.max_response_bytes
        iter_content = getattr(response, "iter_content", None)
        if callable(iter_content):
            chunks: list[bytes] = []
            total = 0
            for chunk in iter_content(chunk_size=8192):
                if not chunk:
                    continue
                total += len(chunk)
                if total > limit:
                    raise AkaInvalidResponseError(
                        "AKA AI response exceeds the size limit"
                    )
                chunks.append(chunk)
            return b"".join(chunks)

        content = getattr(response, "content", b"") or b""
        if len(content) > limit:
            raise AkaInvalidResponseError("AKA AI response exceeds the size limit")
        return content

    def _parse_completion(
        self,
        body: bytes,
        headers: Mapping[str, Any],
        started: float,
    ) -> AkaCompletion:
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AkaInvalidResponseError("AKA AI returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise AkaInvalidResponseError("AKA AI returned a non-object JSON payload")

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AkaInvalidResponseError("AKA AI returned no completion choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise AkaInvalidResponseError("AKA AI returned an invalid choice payload")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise AkaInvalidResponseError("AKA AI returned no assistant message")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AkaInvalidResponseError("AKA AI returned an empty assistant message")

        usage = data.get("usage")
        if not isinstance(usage, dict):
            usage = {}

        latency_ms = max(0, int((self._clock() - started) * 1000))
        return AkaCompletion(
            id=str(data.get("id") or ""),
            model=str(data.get("model") or self.config.models[0]),
            content=content,
            finish_reason=str(first_choice.get("finish_reason") or ""),
            prompt_tokens=self._int_or_none(usage.get("prompt_tokens")),
            completion_tokens=self._int_or_none(usage.get("completion_tokens")),
            total_tokens=self._int_or_none(usage.get("total_tokens")),
            request_id=(
                self._string_or_none(self._get_header(headers, "x-request-id"))
                or self._string_or_none(data.get("request_id"))
            ),
            system_fingerprint=self._string_or_none(data.get("system_fingerprint")),
            latency_ms=latency_ms,
        )

    def _error_from_response(
        self,
        status_code: int,
        headers: Mapping[str, Any],
        body: bytes,
    ) -> AkaError:
        message, code, request_id = self._extract_error(body)
        message = self._redact(message)
        code = self._redact(code)
        retry_after = self._parse_retry_after(headers)
        header_request_id = self._string_or_none(
            self._get_header(headers, "x-request-id")
        )
        request_id = request_id or header_request_id

        if status_code == 429:
            return AkaRateLimitError(
                message or "AKA AI rate limit exceeded",
                status_code=status_code,
                code=code or "rate_limit_exceeded",
                request_id=request_id,
                retry_after=retry_after,
            )
        if status_code in _TRANSIENT_HTTP_STATUSES:
            return AkaServerError(
                message or f"AKA AI transient error (HTTP {status_code})",
                status_code=status_code,
                code=code,
                request_id=request_id,
                retry_after=retry_after,
            )
        if status_code in _CONFIG_ERROR_STATUSES:
            return AkaConfigurationError(
                message or f"AKA AI rejected the request (HTTP {status_code})",
                status_code=status_code,
                code=code,
                request_id=request_id,
            )
        if status_code >= 500:
            return AkaServerError(
                message or f"AKA AI server error (HTTP {status_code})",
                status_code=status_code,
                code=code,
                request_id=request_id,
                retry_after=retry_after,
            )
        return AkaConfigurationError(
            message or f"AKA AI unexpected HTTP status {status_code}",
            status_code=status_code,
            code=code,
            request_id=request_id,
        )

    def _redact(self, value: str) -> str:
        """Defence in depth: never let the API key ride an error message."""
        key = self.config.api_key
        if key and key in value:
            return value.replace(key, "[redacted]")
        return value

    @staticmethod
    def _extract_error(body: bytes) -> tuple[str, str, str | None]:
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "AKA AI returned an unreadable error response", "", None
        if not isinstance(data, dict):
            return "AKA AI returned an invalid error response", "", None

        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message") or ""
            code = error.get("code") or error.get("type") or ""
            request_id = error.get("request_id") or data.get("request_id")
        else:
            message = data.get("detail") or data.get("message") or ""
            code = data.get("code") or ""
            request_id = data.get("request_id")

        return (
            str(message)[:500] or "AKA AI request failed",
            str(code)[:64],
            str(request_id)[:128] if request_id else None,
        )

    @staticmethod
    def _parse_retry_after(headers: Mapping[str, Any]) -> float | None:
        raw = AkaAIClient._get_header(headers, "retry-after")
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("ascii", "ignore")
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            pass
        try:
            retry_at = parsedate_to_datetime(str(raw))
        except (TypeError, ValueError):
            return None
        if retry_at is None:
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())

    @staticmethod
    def _get_header(headers: Mapping[str, Any], name: str) -> Any | None:
        expected = name.lower()
        for key, value in headers.items():
            if str(key).lower() == expected:
                return value
        return None

    @staticmethod
    def _int_or_none(value: Any) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _string_or_none(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _validate_messages(
        messages: Sequence[Mapping[str, Any]],
    ) -> None:
        if not messages:
            raise ValueError("messages must not be empty")
        for message in messages:
            if not isinstance(message, Mapping):
                raise ValueError("each message must be a mapping")
            role = message.get("role")
            content = message.get("content")
            if role not in _ALLOWED_ROLES:
                raise ValueError("message role must be system, user, or assistant")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("message content must be a non-empty string")
