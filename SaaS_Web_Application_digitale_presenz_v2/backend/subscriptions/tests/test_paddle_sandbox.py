import io
import os
import tempfile
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from subscriptions.models import Plan
from subscriptions.pricing import PLAN_CATALOGUE


def seed_plans():
    for entry in PLAN_CATALOGUE:
        Plan.objects.update_or_create(
            tier=entry["tier"],
            defaults={k: v for k, v in entry.items() if k != "tier"},
        )


def fake_response(payload):
    response = type("Response", (), {})()
    response.status_code = 200
    response.text = ""
    response.json = lambda: {"data": payload}
    return response


@override_settings(
    PADDLE_API_KEY="pdl_sdbx_test",
    PADDLE_API_URL="https://sandbox-api.paddle.com",
    PADDLE_ENVIRONMENT="sandbox",
)
class CreatePaddleSandboxTest(TestCase):
    def setUp(self):
        seed_plans()
        self.created_products = 0
        self.created_prices = 0

    def fake_request(
        self, method, url, json=None, params=None, headers=None, timeout=None
    ):
        path = url.split("sandbox-api.paddle.com", 1)[1]
        if method == "GET" and path.startswith("/products"):
            return fake_response([])
        if method == "GET" and path.startswith("/prices"):
            return fake_response([])
        if method == "POST" and path == "/products":
            self.created_products += 1
            return fake_response({"id": f"pro_{self.created_products}"})
        if method == "POST" and path == "/prices":
            self.created_prices += 1
            return fake_response({"id": f"pri_{self.created_prices}"})
        raise AssertionError(f"Unexpected Paddle call: {method} {path}")

    @patch("subscriptions.management.commands.create_paddle_sandbox.requests.request")
    def test_prices_are_created_from_catalogue_and_mapped(self, request_mock):
        request_mock.side_effect = self.fake_request
        call_command("create_paddle_sandbox", stdout=io.StringIO())

        self.assertEqual(self.created_products, 3)
        self.assertEqual(self.created_prices, 6)
        for tier in ("pro", "business", "agency"):
            plan = Plan.objects.get(tier=tier)
            self.assertTrue(plan.external_price_id_monthly.startswith("pri_"))
            self.assertTrue(plan.external_price_id_yearly.startswith("pri_"))
        self.assertFalse(Plan.objects.get(tier="free").external_price_id_monthly)

    def test_missing_api_key_is_refused(self):
        with override_settings(PADDLE_API_KEY=""):
            with self.assertRaises(CommandError):
                call_command("create_paddle_sandbox", stdout=io.StringIO())

    def test_live_api_requires_explicit_flag(self):
        with override_settings(PADDLE_API_URL="https://api.paddle.com"):
            with self.assertRaises(CommandError):
                call_command("create_paddle_sandbox", stdout=io.StringIO())

    @patch("subscriptions.management.commands.create_paddle_sandbox.requests.request")
    def test_webhook_secret_is_written_but_never_printed(self, request_mock):
        def side_effect(
            method, url, json=None, params=None, headers=None, timeout=None
        ):
            path = url.split("sandbox-api.paddle.com", 1)[1]
            if method == "GET" and path.startswith("/notification-settings"):
                return fake_response([])
            if method == "POST" and path == "/notification-settings":
                return fake_response(
                    {"id": "ntf_1", "endpoint_secret_key": "pdl_ntfset_secret"}
                )
            raise AssertionError(f"Unexpected Paddle call: {method} {path}")

        request_mock.side_effect = side_effect
        with tempfile.TemporaryDirectory() as directory:
            secret_path = os.path.join(directory, "webhook.secret")
            output = io.StringIO()
            call_command(
                "create_paddle_sandbox",
                "--skip-products",
                "--webhook-url",
                "https://demo.trycloudflare.com/api/v1/webhooks/paddle/",
                "--secret-file",
                secret_path,
                stdout=output,
            )
            with open(secret_path, encoding="utf-8") as handle:
                self.assertEqual(handle.read().strip(), "pdl_ntfset_secret")
            self.assertEqual(os.stat(secret_path).st_mode & 0o777, 0o600)
            self.assertNotIn("pdl_ntfset_secret", output.getvalue())
