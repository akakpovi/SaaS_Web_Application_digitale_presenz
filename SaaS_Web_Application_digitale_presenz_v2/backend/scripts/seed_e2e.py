#!/usr/bin/env python3
"""Create the minimal data required by the authenticated French E2E checks.

Run inside the backend container, from the repository root:

    docker compose exec -T \
      -e E2E_EMAIL -e E2E_PASSWORD -e E2E_WEBSITE_ID \
      web python scripts/seed_e2e.py

The script is idempotent and never prints or stores the password. It creates
the QA account and a website owned by it. When E2E_WEBSITE_ID is set, the
website is created with that exact primary key so Playwright can use the CI
secret without a discovery step.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import NoReturn

import django

# The script is executed from /app as `python scripts/seed_e2e.py`; Python
# puts /app/scripts (not /app) on sys.path, so make the Django project importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import transaction  # noqa: E402

from subscriptions.models import Plan, Subscription  # noqa: E402
from subscriptions.pricing import PLAN_CATALOGUE  # noqa: E402
from websites.models import Website  # noqa: E402

DEFAULT_DOMAIN = "e2e.presence.local"
DEFAULT_NAME = "Presence E2E QA"


def fail(message: str) -> NoReturn:
    raise SystemExit(f"seed-e2e: {message}")


def required_env(name: str, *, strip: bool = False) -> str:
    raw = os.environ.get(name, "")
    value = raw.strip() if strip else raw
    if not value.strip():
        fail(f"{name} is required")
    return value


def run_seed() -> None:
    email = required_env("E2E_EMAIL", strip=True).lower()
    # Keep the password byte-for-byte: spaces are valid password characters.
    password = required_env("E2E_PASSWORD")

    website_id_raw = os.environ.get("E2E_WEBSITE_ID", "").strip()
    website_id: int | None = None
    if website_id_raw:
        try:
            website_id = int(website_id_raw)
        except ValueError:
            fail("E2E_WEBSITE_ID must be an integer")
        if website_id <= 0:
            fail("E2E_WEBSITE_ID must be positive")

    domain = (
        os.environ.get("E2E_WEBSITE_DOMAIN", DEFAULT_DOMAIN).strip().lower().rstrip(".")
    )
    display_name = os.environ.get("E2E_WEBSITE_NAME", DEFAULT_NAME).strip()
    if not domain:
        fail("E2E_WEBSITE_DOMAIN must not be empty")

    User = get_user_model()

    with transaction.atomic():
        # A fresh CI database has no plans. Seed the whole catalogue with the
        # same source of truth as `create_plans`, so pricing and subscriptions
        # work before the QA account is created. Keep any provider price IDs
        # already stored on existing plans: they are not part of the catalogue.
        plans: dict[str, Plan] = {}
        plans_created = 0
        for entry in PLAN_CATALOGUE:
            plan_data = dict(entry)
            plan_data["tier"] = Plan.Tier(plan_data["tier"])
            plan_data["is_active"] = True
            plan, plan_created = Plan.objects.update_or_create(
                tier=plan_data["tier"],
                defaults=plan_data,
            )
            plans[plan.tier] = plan
            plans_created += int(plan_created)
        free_plan = plans[Plan.Tier.FREE]
        # D2/D4 create and delete a second website. A Free plan only allows one
        # site, so a seeded QA account with an existing site would receive a
        # 403 quota error. When E2E_WEBSITE_ID is set (the CI path), give the QA
        # account an Agency plan; local/internal plans (e.g. ``qa``) are kept.
        qa_plan = plans[Plan.Tier.AGENCY] if website_id is not None else None

        user = User.objects.filter(email__iexact=email).first()
        created_user = user is None
        if user is None:
            user = User(email=email)
        user.email = email
        user.is_active = True
        user.is_email_verified = True
        # `admin.spec.ts` logs into Django admin with the same QA account.
        # These flags are scoped to the disposable E2E database/account and
        # make the admin checks independent from a manually prepared fixture.
        user.is_staff = True
        user.is_superuser = True
        if not user.full_name:
            user.full_name = "Presence QA"
        user.set_password(password)
        user.save()

        # Fresh accounts get this from the signal. Keep the seed idempotent
        # and repair an existing QA account that predates the plan catalogue.
        subscription, subscription_created = Subscription.objects.get_or_create(
            user=user,
            defaults={
                "plan": qa_plan or free_plan,
                "status": Subscription.Status.ACTIVE,
            },
        )
        if qa_plan is not None and subscription.plan_id == free_plan.pk:
            # The user post_save signal has already attached Free. Upgrade it
            # so the website CRUD tests can exercise add/delete without a
            # quota failure; do not overwrite a real local subscription.
            subscription.plan = qa_plan
            subscription.status = Subscription.Status.ACTIVE
            subscription.cancelled_at = None
            subscription.save(
                update_fields=["plan", "status", "cancelled_at", "updated_at"]
            )
        elif (
            subscription.plan_id == free_plan.pk
            and subscription.status != Subscription.Status.ACTIVE
        ):
            subscription.status = Subscription.Status.ACTIVE
            subscription.cancelled_at = None
            subscription.save(update_fields=["status", "cancelled_at", "updated_at"])

        if website_id is not None:
            website = Website.objects.filter(pk=website_id).first()
            if website is None:
                website = Website(
                    pk=website_id,
                    owner=user,
                    domain=domain,
                    display_name=display_name,
                    is_active=True,
                    is_guest=False,
                )
                website.save(force_insert=True)
                created_website = True
            else:
                if website.owner_id != user.pk:
                    fail(
                        f"website {website_id} belongs to owner {website.owner_id}, "
                        "not to the seeded account"
                    )
                created_website = False
                if website.organization_id is None:
                    website.save()
        else:
            website, created_website = Website.objects.get_or_create(
                owner=user,
                domain=domain,
                defaults={
                    "display_name": display_name,
                    "is_active": True,
                    "is_guest": False,
                },
            )
            if website.organization_id is None:
                website.save()

    print(
        f"seed-e2e: plans ensured={len(plans)} created={plans_created} "
        f"tiers={','.join(sorted(plans))}"
    )
    print(
        f"seed-e2e: user {'created' if created_user else 'updated'} id={user.pk} "
        "staff=True superuser=True"
    )
    print(
        f"seed-e2e: website {'created' if created_website else 'reused'} "
        f"id={website.pk}"
    )
    print(
        f"seed-e2e: subscription "
        f"{'created' if subscription_created else 'reused'} "
        f"tier={subscription.plan.tier}"
    )
    print(f"E2E_WEBSITE_ID={website.pk}")


def main() -> None:
    run_seed()


if __name__ == "__main__":
    sys.exit(main())
