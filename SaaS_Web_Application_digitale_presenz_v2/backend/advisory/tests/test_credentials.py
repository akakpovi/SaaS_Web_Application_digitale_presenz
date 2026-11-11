"""The gateway never returns 401 for a bad key: it serves guest mode.

These tests pin the detection that turns that silent downgrade into an
explicit, non-retryable configuration failure, and the shared cooldown that
stops every worker from burning the 3-request guest quota.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import User
from advisory.models import AIRecommendationRun
from advisory.services.aka_client import (
    AkaAIClient,
    AkaAuthenticationError,
    AkaConfig,
    AkaRateLimitError,
    AkaCompletion,
)
from advisory.services.advisor import generate_recommendations_for_scan
from advisory.services.factory import (
    aka_credentials_marked_invalid,
    clear_aka_credentials_invalid,
)
from scans.models import Scan
from websites.models import Website

GUEST_HEADERS = {
    "content-type": "application/json",
    "x-ratelimit-limit": "3",
    "x-ratelimit-remaining": "2",
}
AUTH_HEADERS = {"content-type": "application/json"}

VALID_BODY = (
    b'{"id":"chatcmpl-1","model":"qwen/qwen3.8-27b","choices":['
    b'{"index":0,"finish_reason":"stop","message":{"role":"assistant",'
    b'"content":"{\\"recommendations\\": []}"}}],'
    b'"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}'
)
GUEST_429_BODY = (
    b'{"error":{"message":"Free limit reached","type":"rate_limit_exceeded",'
    b'"code":"guest_quota_exceeded"}}'
)


class FakeResponse:
    def __init__(self, status_code: int, headers: dict, body: bytes) -> None:
        self.status_code = status_code
        self.headers = headers
        self._body = body

    def iter_content(self, chunk_size: int = 8192):
        yield self._body

    def close(self) -> None:
        return None


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls = 0

    def post(self, *args, **kwargs) -> FakeResponse:
        self.calls += 1
        return self.response

    def mount(self, *args, **kwargs) -> None:
        return None

    def close(self) -> None:
        return None


def _client(response: FakeResponse) -> tuple[AkaAIClient, FakeSession]:
    session = FakeSession(response)
    config = AkaConfig(
        api_key="test-key",
        models=("model-a",),
        max_retries=2,
        backoff_base=0,
    )
    return (
        AkaAIClient(config, session=session, sleep=lambda _seconds: None),
        session,
    )


class GuestModeDetectionTests(TestCase):
    def test_guest_200_is_a_configuration_failure_and_is_not_retried(self) -> None:
        client, session = _client(FakeResponse(200, GUEST_HEADERS, VALID_BODY))

        with self.assertRaises(AkaAuthenticationError) as caught:
            client.chat([{"role": "user", "content": "hello"}], model="model-a")

        self.assertEqual(caught.exception.code, "invalid_api_key")
        self.assertEqual(caught.exception.status_code, 200)
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(session.calls, 1, "a bad key must not be retried")

    def test_guest_429_is_reported_as_a_bad_key_not_a_quota_issue(self) -> None:
        headers = dict(GUEST_HEADERS)
        headers["retry-after"] = "86400"
        client, session = _client(FakeResponse(429, headers, GUEST_429_BODY))

        with self.assertRaises(AkaAuthenticationError):
            client.chat([{"role": "user", "content": "hello"}], model="model-a")

        self.assertEqual(session.calls, 1)

    def test_guest_quota_code_without_header_still_fails_credentials(self) -> None:
        client, session = _client(FakeResponse(429, {}, GUEST_429_BODY))

        with self.assertRaises(AkaAuthenticationError):
            client.chat([{"role": "user", "content": "hello"}], model="model-a")

        self.assertEqual(session.calls, 1)

    def test_authenticated_200_succeeds(self) -> None:
        client, session = _client(FakeResponse(200, AUTH_HEADERS, VALID_BODY))

        completion = client.chat(
            [{"role": "user", "content": "hello"}], model="model-a"
        )

        self.assertIsInstance(completion, AkaCompletion)
        self.assertEqual(session.calls, 1)

    def test_authenticated_429_stays_a_rate_limit(self) -> None:
        body = b'{"error":{"message":"slow down","code":"rate_limit_exceeded"}}'
        headers = dict(AUTH_HEADERS)
        headers["retry-after"] = "86400"
        client, session = _client(FakeResponse(429, headers, body))

        with self.assertRaises(AkaRateLimitError):
            client.chat([{"role": "user", "content": "hello"}], model="model-a")

        # Long Retry-After is surfaced immediately, never slept through.
        self.assertEqual(session.calls, 1)


class AdvisorCredentialTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.user = User.objects.create_user(
            email="credential-advisor@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(
            owner=self.user, domain="credential-advisor.example"
        )

    def tearDown(self) -> None:
        cache.clear()

    def _scan(self, domain: str = "credential-advisor.example") -> Scan:
        website = self.website
        if domain != self.website.domain:
            website = Website.objects.create(owner=self.user, domain=domain)
        return Scan.objects.create(
            website=website,
            status=Scan.Status.COMPLETED,
            health_score=50,
        )

    def test_auth_error_marks_the_run_and_the_shared_cache(self) -> None:
        scan = self._scan()
        auth_error = AkaAuthenticationError(
            "guest mode", status_code=200, code="invalid_api_key"
        )
        client = SimpleNamespace(
            config=SimpleNamespace(models=("model-a",)),
            chat=mock.Mock(side_effect=auth_error),
        )

        result = generate_recommendations_for_scan(scan.pk, client=client)

        run = AIRecommendationRun.objects.get(scan=scan)
        self.assertEqual(run.status, AIRecommendationRun.Status.FAILED)
        self.assertEqual(run.error_code, "invalid_api_key")
        self.assertTrue(result.used_fallback)
        self.assertFalse(result.should_retry)
        self.assertIsNotNone(aka_credentials_marked_invalid())
        self.assertEqual(client.chat.call_count, 1, "models are not retried")

    @override_settings(AKA_AI_AUTH_FAILURE_COOLDOWN=900)
    def test_cached_invalid_key_refuses_without_any_network_call(self) -> None:
        scan = self._scan("credential-advisor-cached.example")
        cache.set(
            "advisory:aka_credentials_invalid",
            {"reason": "invalid_api_key"},
            timeout=900,
        )

        with mock.patch(
            "advisory.services.advisor.build_aka_client",
            side_effect=AssertionError("must not build a client"),
        ) as build:
            result = generate_recommendations_for_scan(scan.pk)

        run = AIRecommendationRun.objects.get(scan=scan)
        self.assertEqual(run.status, AIRecommendationRun.Status.FAILED)
        self.assertEqual(run.error_code, "invalid_api_key")
        self.assertTrue(result.used_fallback)
        build.assert_not_called()

    def test_successful_probe_clears_the_cache(self) -> None:
        cache.set("advisory:aka_credentials_invalid", {"reason": "old"}, timeout=900)
        clear_aka_credentials_invalid()
        self.assertIsNone(aka_credentials_marked_invalid())


class CheckAkaKeyCommandTests(TestCase):
    def tearDown(self) -> None:
        cache.clear()

    def test_guest_mode_fails_the_command(self) -> None:
        client, _session = _client(FakeResponse(200, GUEST_HEADERS, VALID_BODY))
        with mock.patch(
            "advisory.management.commands.check_aka_key.build_aka_client",
            return_value=client,
        ):
            with self.assertRaises(CommandError):
                call_command("check_aka_key")

    def test_authenticated_probe_succeeds(self) -> None:
        client, _session = _client(FakeResponse(200, AUTH_HEADERS, VALID_BODY))
        with mock.patch(
            "advisory.management.commands.check_aka_key.build_aka_client",
            return_value=client,
        ):
            call_command("check_aka_key")
