"""Unit tests for the AKA IA HTTP client.

Every network call is faked.  No test reads the real API key, opens a socket,
or sleeps: retry delays are captured through an injected ``sleep`` callable.
"""

from __future__ import annotations

import json
import unittest
from typing import Any

import requests
from requests.structures import CaseInsensitiveDict

from advisory.services.aka_client import (
    AkaAIClient,
    AkaCircuitOpenError,
    AkaCompletion,
    AkaConfig,
    AkaConfigurationError,
    AkaInvalidResponseError,
    AkaRateLimitError,
    AkaServerError,
    AkaTimeoutError,
)

TEST_KEY = "sk-test-never-log-this-key"
TARGET_MODEL = "groq/qwen/qwen3.8-27b"
SECOND_MODEL = "ddgw/gpt-5.4-mini"
MESSAGES = [{"role": "user", "content": "ping"}]


def completion_payload(content: str = "AKA_OK") -> dict[str, Any]:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1792817003,
        "model": "qwen/qwen3.8-27b",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
        "usage": {
            "prompt_tokens": 35,
            "completion_tokens": 4,
            "total_tokens": 39,
        },
        "system_fingerprint": "fp-test",
    }


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        *,
        payload: dict[str, Any] | None = None,
        body: bytes | str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = CaseInsensitiveDict(headers or {})
        if body is not None:
            self._body = body if isinstance(body, bytes) else body.encode()
        elif payload is not None:
            self._body = json.dumps(payload).encode()
        else:
            self._body = b""
        self.closed = False

    def iter_content(self, chunk_size: int = 8192):
        for index in range(0, len(self._body), chunk_size):
            yield self._body[index : index + chunk_size]

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, *responses: FakeResponse | BaseException) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if not self.responses:
            raise AssertionError("Unexpected HTTP call")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def make_config(**overrides: Any) -> AkaConfig:
    values: dict[str, Any] = {
        "api_key": TEST_KEY,
        "base_url": "https://aka.test",
        "models": (TARGET_MODEL, SECOND_MODEL),
        "max_retries": 2,
        "connect_timeout": 1.0,
        "read_timeout": 1.0,
        "backoff_base": 2.0,
        "backoff_max": 60.0,
        "max_retry_after": 300.0,
        "temperature": 0.2,
        "max_tokens": 900,
        "max_response_bytes": 100_000,
        "circuit_failure_threshold": 5,
        "circuit_recovery_seconds": 300.0,
    }
    values.update(overrides)
    return AkaConfig(**values)


def make_client(
    session: FakeSession,
    *,
    config: AkaConfig | None = None,
    sleeps: list[float] | None = None,
    clock=None,
    random_fn=None,
) -> tuple[AkaAIClient, list[float]]:
    captured = sleeps if sleeps is not None else []
    client = AkaAIClient(
        config or make_config(),
        session=session,
        sleep=captured.append,
        clock=clock or (lambda: 0.0),
        random_fn=random_fn or (lambda: 0.0),
    )
    return client, captured


class AkaClientConfigurationTests(unittest.TestCase):
    def test_missing_key_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AkaConfig(api_key="")

    def test_non_https_base_url_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AkaConfig(api_key=TEST_KEY, base_url="http://aka.test")

    def test_bearer_prefix_is_normalised(self) -> None:
        config = AkaConfig(api_key=f"Bearer {TEST_KEY}")
        self.assertEqual(config.api_key, TEST_KEY)

    def test_models_are_ordered_and_deduplicated(self) -> None:
        config = AkaConfig(
            api_key=TEST_KEY,
            models=(SECOND_MODEL, TARGET_MODEL, SECOND_MODEL),
        )
        self.assertEqual(config.models, (SECOND_MODEL, TARGET_MODEL))

    def test_empty_models_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AkaConfig(api_key=TEST_KEY, models=())

    def test_repr_never_contains_the_api_key(self) -> None:
        config = make_config()
        client, _ = make_client(FakeSession())
        self.assertNotIn(TEST_KEY, repr(config))
        self.assertNotIn(TEST_KEY, repr(client))
        self.assertIn(TARGET_MODEL, repr(client))

    def test_empty_messages_are_rejected_before_any_call(self) -> None:
        session = FakeSession()
        client, sleeps = make_client(session)
        with self.assertRaises(ValueError):
            client.chat([])
        self.assertEqual(session.calls, [])
        self.assertEqual(sleeps, [])

    def test_invalid_role_and_empty_content_are_rejected(self) -> None:
        client, _ = make_client(FakeSession())
        with self.assertRaises(ValueError):
            client.chat([{"role": "tool", "content": "x"}])
        with self.assertRaises(ValueError):
            client.chat([{"role": "user", "content": "   "}])


class AkaClientSuccessTests(unittest.TestCase):
    def test_success_parses_openai_payload_and_sends_bearer(self) -> None:
        response = FakeResponse(
            payload=completion_payload(),
            headers={"x-request-id": "req-success"},
        )
        session = FakeSession(response)
        client, sleeps = make_client(session)

        result = client.chat(
            MESSAGES,
            temperature=0,
            max_tokens=16,
        )

        self.assertIsInstance(result, AkaCompletion)
        self.assertEqual(result.content, "AKA_OK")
        self.assertEqual(result.model, "qwen/qwen3.8-27b")
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.prompt_tokens, 35)
        self.assertEqual(result.completion_tokens, 4)
        self.assertEqual(result.total_tokens, 39)
        self.assertEqual(result.request_id, "req-success")
        self.assertEqual(result.system_fingerprint, "fp-test")
        self.assertEqual(sleeps, [])
        self.assertTrue(response.closed)

        self.assertEqual(len(session.calls), 1)
        call = session.calls[0]
        self.assertEqual(call["url"], "https://aka.test/v1/chat/completions")
        self.assertEqual(
            call["headers"]["Authorization"], f"Bearer {TEST_KEY}"
        )
        self.assertEqual(call["timeout"], (1.0, 1.0))
        self.assertFalse(call["allow_redirects"])
        self.assertTrue(call["stream"])
        self.assertEqual(call["json"]["model"], TARGET_MODEL)
        self.assertEqual(call["json"]["messages"], MESSAGES)
        self.assertEqual(call["json"]["temperature"], 0)
        self.assertEqual(call["json"]["max_tokens"], 16)
        self.assertFalse(call["json"]["stream"])

    def test_chat_can_select_the_second_model(self) -> None:
        session = FakeSession(FakeResponse(payload=completion_payload()))
        client, _ = make_client(
            session,
            config=make_config(models=(TARGET_MODEL, SECOND_MODEL)),
        )

        client.chat(MESSAGES, model=SECOND_MODEL)

        self.assertEqual(len(session.calls), 1)
        self.assertEqual(session.calls[0]["json"]["model"], SECOND_MODEL)

    def test_unknown_model_is_rejected_before_http(self) -> None:
        session = FakeSession()
        client, _ = make_client(session)

        with self.assertRaises(ValueError):
            client.chat(MESSAGES, model="unknown/model")

        self.assertEqual(session.calls, [])


class AkaClientErrorTests(unittest.TestCase):
    def test_401_is_configuration_error_and_is_not_retried(self) -> None:
        session = FakeSession(
            FakeResponse(
                401,
                payload={
                    "error": {
                        "message": "Invalid API key",
                        "code": "invalid_api_key",
                        "request_id": "req-401",
                    }
                },
            )
        )
        client, sleeps = make_client(session)

        with self.assertRaises(AkaConfigurationError) as context:
            client.chat(MESSAGES)

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.code, "invalid_api_key")
        self.assertEqual(context.exception.request_id, "req-401")
        self.assertNotIn(TEST_KEY, str(context.exception))
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(sleeps, [])

    def test_real_401_shape_uses_type_when_code_is_null(self) -> None:
        # Fixture copied from the live gateway probe (2026-10-24).
        session = FakeSession(
            FakeResponse(
                401,
                payload={
                    "error": {
                        "message": "Invalid API key.",
                        "type": "AuthenticationFailed",
                        "param": None,
                        "code": None,
                        "request_id": "028abb0e39524398a16b0dc76b009c06",
                    }
                },
            )
        )
        client, sleeps = make_client(session)

        with self.assertRaises(AkaConfigurationError) as context:
            client.chat(MESSAGES)

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.code, "AuthenticationFailed")
        self.assertEqual(
            context.exception.request_id,
            "028abb0e39524398a16b0dc76b009c06",
        )
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(sleeps, [])

    def test_provider_message_cannot_echo_the_api_key(self) -> None:
        session = FakeSession(
            FakeResponse(
                401,
                payload={
                    "error": {
                        "message": f"Invalid key {TEST_KEY}",
                        "type": "AuthenticationFailed",
                    }
                },
            )
        )
        client, _ = make_client(session)

        with self.assertRaises(AkaConfigurationError) as context:
            client.chat(MESSAGES)

        self.assertNotIn(TEST_KEY, str(context.exception))
        self.assertIn("[redacted]", str(context.exception))

    def test_three_retries_follow_the_2_4_8_schedule(self) -> None:
        session = FakeSession(
            FakeResponse(500, payload={"error": {"message": "boom"}}),
            FakeResponse(500, payload={"error": {"message": "boom"}}),
            FakeResponse(500, payload={"error": {"message": "boom"}}),
            FakeResponse(payload=completion_payload()),
        )
        client, sleeps = make_client(
            session, config=make_config(max_retries=3)
        )

        result = client.chat(MESSAGES)

        self.assertEqual(result.content, "AKA_OK")
        self.assertEqual(sleeps, [2.0, 4.0, 8.0])
        self.assertEqual(len(session.calls), 4)

    def test_400_model_not_found_is_not_retried(self) -> None:
        session = FakeSession(
            FakeResponse(
                400,
                payload={
                    "error": {
                        "message": "The model does not exist.",
                        "code": "model_not_found",
                    }
                },
            )
        )
        client, sleeps = make_client(session)

        with self.assertRaises(AkaConfigurationError) as context:
            client.chat(MESSAGES)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.code, "model_not_found")
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(sleeps, [])

    def test_400_403_404_are_configuration_errors(self) -> None:
        for status_code in (400, 403, 404):
            with self.subTest(status_code=status_code):
                session = FakeSession(
                    FakeResponse(
                        status_code,
                        payload={
                            "error": {
                                "message": "configuration problem",
                                "code": "config_error",
                            }
                        },
                    )
                )
                client, sleeps = make_client(session)
                with self.assertRaises(AkaConfigurationError):
                    client.chat(MESSAGES)
                self.assertEqual(len(session.calls), 1)
                self.assertEqual(sleeps, [])

    def test_429_with_short_retry_after_retries_once(self) -> None:
        session = FakeSession(
            FakeResponse(
                429,
                payload={
                    "error": {
                        "message": "slow down",
                        "code": "rate_limit_exceeded",
                    }
                },
                headers={"Retry-After": "1"},
            ),
            FakeResponse(payload=completion_payload()),
        )
        client, sleeps = make_client(session)

        result = client.chat(MESSAGES)

        self.assertEqual(result.content, "AKA_OK")
        self.assertEqual(sleeps, [1.0])
        self.assertEqual(len(session.calls), 2)

    def test_429_without_retry_after_uses_exponential_backoff(self) -> None:
        session = FakeSession(
            FakeResponse(
                429,
                payload={
                    "error": {
                        "message": "slow down",
                        "code": "rate_limit_exceeded",
                    }
                },
            ),
            FakeResponse(
                429,
                payload={
                    "error": {
                        "message": "slow down",
                        "code": "rate_limit_exceeded",
                    }
                },
            ),
            FakeResponse(payload=completion_payload()),
        )
        client, sleeps = make_client(session)

        result = client.chat(MESSAGES)

        self.assertEqual(result.content, "AKA_OK")
        self.assertEqual(sleeps, [2.0, 4.0])
        self.assertEqual(len(session.calls), 3)

    def test_429_with_long_retry_after_is_not_retried(self) -> None:
        session = FakeSession(
            FakeResponse(
                429,
                payload={
                    "error": {
                        "message": "slow down",
                        "code": "rate_limit_exceeded",
                    }
                },
                headers={"Retry-After": "86400"},
            )
        )
        client, sleeps = make_client(session)

        with self.assertRaises(AkaRateLimitError) as context:
            client.chat(MESSAGES)

        self.assertEqual(context.exception.retry_after, 86400.0)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(sleeps, [])

    def test_5xx_uses_exponential_backoff_with_jitter(self) -> None:
        session = FakeSession(
            FakeResponse(500, payload={"error": {"message": "boom"}}),
            FakeResponse(500, payload={"error": {"message": "boom"}}),
            FakeResponse(payload=completion_payload()),
        )
        client, sleeps = make_client(session)

        result = client.chat(MESSAGES)

        self.assertEqual(result.content, "AKA_OK")
        self.assertEqual(sleeps, [2.0, 4.0])
        self.assertEqual(len(session.calls), 3)

    def test_5xx_exhaustion_raises_server_error(self) -> None:
        session = FakeSession(
            FakeResponse(500, payload={"error": {"message": "boom"}}),
            FakeResponse(500, payload={"error": {"message": "boom"}}),
            FakeResponse(500, payload={"error": {"message": "boom"}}),
        )
        client, sleeps = make_client(session)

        with self.assertRaises(AkaServerError):
            client.chat(MESSAGES)

        self.assertEqual(len(session.calls), 3)
        self.assertEqual(sleeps, [2.0, 4.0])

    def test_timeout_is_retried_then_succeeds(self) -> None:
        session = FakeSession(
            requests.Timeout("slow"),
            FakeResponse(payload=completion_payload()),
        )
        client, sleeps = make_client(session)

        result = client.chat(MESSAGES)

        self.assertEqual(result.content, "AKA_OK")
        self.assertEqual(sleeps, [2.0])
        self.assertEqual(len(session.calls), 2)

    def test_timeout_exhaustion_raises_timeout_error(self) -> None:
        session = FakeSession(
            requests.Timeout("slow"),
            requests.Timeout("slow"),
        )
        client, sleeps = make_client(
            session, config=make_config(max_retries=1)
        )

        with self.assertRaises(AkaTimeoutError):
            client.chat(MESSAGES)

        self.assertEqual(len(session.calls), 2)
        self.assertEqual(sleeps, [2.0])

    def test_invalid_json_is_not_retried(self) -> None:
        session = FakeSession(FakeResponse(200, body=b"not-json"))
        client, sleeps = make_client(session)

        with self.assertRaises(AkaInvalidResponseError):
            client.chat(MESSAGES)

        self.assertEqual(len(session.calls), 1)
        self.assertEqual(sleeps, [])

    def test_empty_choices_are_rejected(self) -> None:
        session = FakeSession(
            FakeResponse(200, payload={"choices": [], "usage": {}})
        )
        client, _ = make_client(session)

        with self.assertRaises(AkaInvalidResponseError):
            client.chat(MESSAGES)

        self.assertEqual(len(session.calls), 1)

    def test_oversized_response_is_rejected(self) -> None:
        session = FakeSession(FakeResponse(200, body=b"x" * 101))
        client, _ = make_client(
            session, config=make_config(max_response_bytes=100)
        )

        with self.assertRaises(AkaInvalidResponseError):
            client.chat(MESSAGES)

        self.assertEqual(len(session.calls), 1)


class AkaClientCircuitBreakerTests(unittest.TestCase):
    def test_circuit_opens_after_threshold_and_recovers(self) -> None:
        now = [0.0]
        session = FakeSession(
            FakeResponse(500, payload={"error": {"message": "boom"}}),
            FakeResponse(500, payload={"error": {"message": "boom"}}),
            FakeResponse(payload=completion_payload()),
        )
        config = make_config(
            max_retries=0,
            circuit_failure_threshold=2,
            circuit_recovery_seconds=60.0,
        )
        client, sleeps = make_client(
            session,
            config=config,
            clock=lambda: now[0],
        )

        with self.assertRaises(AkaServerError):
            client.chat(MESSAGES)
        with self.assertRaises(AkaServerError):
            client.chat(MESSAGES)

        with self.assertRaises(AkaCircuitOpenError) as context:
            client.chat(MESSAGES)
        self.assertGreater(context.exception.retry_after or 0, 0)

        # The circuit is open: no third HTTP call was made.
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(sleeps, [])

        now[0] = 61.0
        result = client.chat(MESSAGES)
        self.assertEqual(result.content, "AKA_OK")
        self.assertEqual(len(session.calls), 3)


class AkaClientLoggingTests(unittest.TestCase):
    def test_retry_logs_never_contain_the_api_key_or_prompt(self) -> None:
        session = FakeSession(
            FakeResponse(500, payload={"error": {"message": "boom"}}),
            FakeResponse(payload=completion_payload()),
        )
        client, _ = make_client(session)

        with self.assertLogs(
            "advisory.services.aka_client", level="WARNING"
        ) as captured:
            client.chat(MESSAGES)

        joined = "\n".join(captured.output)
        self.assertIn("aka_ai_retry", joined)
        self.assertNotIn(TEST_KEY, joined)
        self.assertNotIn("ping", joined)


if __name__ == "__main__":
    unittest.main()
