"""Regression tests for the CI E2E seed script."""

from __future__ import annotations

import io
import os
from contextlib import redirect_stdout
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from subscriptions.models import Plan, Subscription
from websites.models import Website

User = get_user_model()

TEST_PASSWORD = "seed-e2e-unit-test-password"
TEST_DOMAIN = "seed-e2e.example"


def run_seed_with(
    *,
    email: str = "seed-e2e@example.test",
    website_id: str = "",
) -> str:
    """Run the seed with isolated environment values and capture its output."""
    env = {
        "E2E_EMAIL": email,
        "E2E_PASSWORD": TEST_PASSWORD,
        "E2E_WEBSITE_ID": website_id,
        "E2E_WEBSITE_DOMAIN": TEST_DOMAIN,
        "E2E_WEBSITE_NAME": "Presence Seed Test",
    }

    # Import lazily: the script performs Django setup at import time, and the
    # test runner must configure the test settings first.
    from scripts.seed_e2e import run_seed

    output = io.StringIO()
    with patch.dict(os.environ, env, clear=False), redirect_stdout(output):
        run_seed()
    return output.getvalue()


class SeedE2ETest(TestCase):
    """Exercise the seed against a clean database transaction."""

    def setUp(self) -> None:
        super().setUp()
        Subscription.objects.all().delete()
        Website.objects.all().delete()
        Plan.objects.all().delete()
        User.objects.all().delete()

    def test_seed_creates_free_plan(self) -> None:
        self.assertFalse(Plan.objects.filter(tier=Plan.Tier.FREE).exists())

        run_seed_with(email="seed-e2e-plan@example.test")

        self.assertTrue(Plan.objects.filter(tier=Plan.Tier.FREE).exists())
        plan = Plan.objects.get(tier=Plan.Tier.FREE)
        self.assertEqual(plan.max_websites, 1)
        self.assertEqual(plan.max_scans_per_month, 10)

    def test_seed_creates_user_with_free_subscription(self) -> None:
        email = "seed-e2e-user@example.test"

        run_seed_with(email=email)

        user = User.objects.get(email=email)
        self.assertTrue(user.check_password(TEST_PASSWORD))
        subscriptions = Subscription.objects.filter(user=user)
        self.assertEqual(subscriptions.count(), 1)
        subscription = subscriptions.get()
        self.assertEqual(subscription.plan.tier, Plan.Tier.FREE)
        self.assertEqual(subscription.status, Subscription.Status.ACTIVE)

    def test_seed_creates_website_for_user(self) -> None:
        email = "seed-e2e-website@example.test"

        run_seed_with(email=email, website_id="999998")

        user = User.objects.get(email=email)
        website = Website.objects.get(pk=999998)
        self.assertEqual(website.owner, user)
        self.assertEqual(website.domain, TEST_DOMAIN)
        self.assertTrue(website.is_active)
        self.assertFalse(website.is_guest)

    def test_seed_is_idempotent(self) -> None:
        email = "seed-e2e-idempotent@example.test"

        run_seed_with(email=email)
        run_seed_with(email=email)

        self.assertEqual(User.objects.filter(email=email).count(), 1)
        user = User.objects.get(email=email)
        self.assertEqual(Subscription.objects.filter(user=user).count(), 1)
        self.assertEqual(Website.objects.filter(owner=user).count(), 1)
        self.assertEqual(Plan.objects.filter(tier=Plan.Tier.FREE).count(), 1)
