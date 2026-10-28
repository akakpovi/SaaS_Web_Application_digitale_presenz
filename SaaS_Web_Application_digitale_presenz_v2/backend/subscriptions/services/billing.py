"""Client Paddle Billing (API + webhooks) — sans SDK externe.

Toutes les opérations passent par l'API REST officielle avec ``requests`` :
création de transaction (checkout hébergé), session du portail client, et
vérification de la signature des webhooks.

Rien n'est facturé si ``BILLING_ENABLED`` / ``BILLING_PROVIDER`` / les clés ne
sont pas configurés : les vues renvoient alors un 503 explicite.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone as dt_timezone

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from subscriptions.models import Plan, Subscription

logger = logging.getLogger(__name__)

#: Tolérance de l'horodatage de signature (anti-rejeu), en secondes.
SIGNATURE_TOLERANCE_SECONDS = 300

#: Délai maximal des appels à l'API Paddle.
REQUEST_TIMEOUT_SECONDS = 15

STATUS_MAP = {
    "active": Subscription.Status.ACTIVE,
    "trialing": Subscription.Status.TRIALING,
    "past_due": Subscription.Status.PAST_DUE,
    "paused": Subscription.Status.PAST_DUE,
    "canceled": Subscription.Status.CANCELLED,
}


class BillingError(Exception):
    """Erreur de facturation générique."""


class BillingNotConfigured(BillingError):
    """Le prestataire ou une clé requise n'est pas configuré."""


class BillingProviderError(BillingError):
    """Le prestataire a refusé la requête ou renvoyé une réponse inexploitable."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def get_provider() -> str:
    return (getattr(settings, "BILLING_PROVIDER", "") or "").strip().lower()


def is_configured(*, require_api_key: bool = True) -> bool:
    """True when a real payment flow can be attempted."""
    if not getattr(settings, "BILLING_ENABLED", False):
        return False
    if get_provider() != "paddle":
        return False
    if require_api_key and not getattr(settings, "PADDLE_API_KEY", ""):
        return False
    return True


def _api_base() -> str:
    return (
        getattr(settings, "PADDLE_API_URL", "") or "https://api.paddle.com"
    ).rstrip("/")


def _api_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.PADDLE_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _post(path: str, payload: dict) -> dict:
    if not is_configured():
        raise BillingNotConfigured("Paddle is not configured.")

    url = f"{_api_base()}{path}"
    try:
        response = requests.post(
            url,
            json=payload,
            headers=_api_headers(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.error("Paddle request failed (%s): %s", path, exc)
        raise BillingProviderError("Payment provider is unreachable.") from exc

    if response.status_code >= 400:
        logger.error(
            "Paddle API error on %s: HTTP %s — %s",
            path,
            response.status_code,
            response.text[:1000],
        )
        raise BillingProviderError(
            f"Payment provider rejected the request (HTTP {response.status_code})."
        )

    try:
        return response.json().get("data") or {}
    except ValueError as exc:
        raise BillingProviderError("Invalid JSON from payment provider.") from exc


# ---------------------------------------------------------------------------
# Checkout & customer portal
# ---------------------------------------------------------------------------


def create_checkout(user, plan: Plan, billing_cycle: str) -> dict:
    """Create a Paddle transaction and return its hosted checkout URL.

    The client never sends an amount: only ``plan_tier`` and ``billing_cycle``.
    The price ID comes from the plan row, which is the single source of truth
    shared with the public pricing API.
    """
    if plan.tier == Plan.Tier.FREE:
        raise BillingNotConfigured("The Free plan does not require checkout.")

    price_id = plan.external_price_id_monthly
    if billing_cycle == Subscription.BillingCycle.YEARLY:
        price_id = plan.external_price_id_yearly
    if not price_id:
        raise BillingNotConfigured(
            f"No {get_provider()} price ID configured for {plan.tier}/{billing_cycle}."
        )

    custom_data = {
        "user_id": str(user.pk),
        "plan_tier": plan.tier,
        "billing_cycle": billing_cycle,
    }

    sub = getattr(user, "subscription", None)
    customer_id = (sub.billing_metadata or {}).get("customer_id") if sub else None

    payload: dict = {
        "items": [{"price_id": price_id, "quantity": 1}],
        "custom_data": custom_data,
        "checkout": {
            "url": f"{settings.FRONTEND_URL}/app/billing?checkout=success",
        },
    }
    if customer_id:
        payload["customer_id"] = customer_id

    data = _post("/transactions", payload)
    checkout_url = (data.get("checkout") or {}).get("url")
    if not checkout_url:
        raise BillingProviderError("Payment provider returned no checkout URL.")

    if sub:
        metadata = dict(sub.billing_metadata or {})
        metadata.update(
            {
                "last_transaction_id": data.get("id"),
                "last_price_id": price_id,
                "environment": getattr(settings, "PADDLE_ENVIRONMENT", "sandbox"),
            }
        )
        sub.billing_provider = get_provider()
        sub.billing_metadata = metadata
        sub.save(update_fields=["billing_provider", "billing_metadata", "updated_at"])

    return {
        "checkout_url": checkout_url,
        "transaction_id": data.get("id"),
        "price_id": price_id,
    }


def cancel_at_period_end(sub: Subscription) -> dict:
    """Ask Paddle to stop renewing at the end of the paid period.

    The local subscription stays ACTIVE until the provider sends
    ``subscription.canceled`` — marking it cancelled immediately would cut a
    customer off while they have already paid for the current period.
    """
    if not sub.external_id:
        raise BillingNotConfigured("No provider subscription attached.")

    data = _post(
        f"/subscriptions/{sub.external_id}/cancel",
        {"effective_from": "next_billing_period"},
    )
    metadata = dict(sub.billing_metadata or {})
    metadata["cancel_at_period_end"] = True
    metadata["scheduled_change"] = data.get("scheduled_change")
    sub.billing_metadata = metadata
    sub.save(update_fields=["billing_metadata", "updated_at"])
    return metadata["scheduled_change"] or {"action": "cancel"}


def create_portal_session(user) -> str:
    """Return a Paddle customer-portal URL (payment method, invoices, cancel)."""
    sub = getattr(user, "subscription", None)
    customer_id = (sub.billing_metadata or {}).get("customer_id") if sub else None
    if not sub or not customer_id:
        raise BillingNotConfigured("No billing account is attached to this user.")

    data = _post(f"/customers/{customer_id}/portal-sessions", {})
    url = (
        ((data.get("urls") or {}).get("general") or {}).get("overview")
        or (data.get("urls") or {}).get("general")
    )
    if not url:
        raise BillingProviderError("Payment provider returned no portal URL.")
    return url


# ---------------------------------------------------------------------------
# Webhook signature
# ---------------------------------------------------------------------------


def verify_paddle_signature(
    raw_body: bytes,
    signature_header: str,
    secret: str,
    *,
    tolerance: int = SIGNATURE_TOLERANCE_SECONDS,
) -> bool:
    """Verify the ``Paddle-Signature`` header (``ts=...;h1=...``).

    HMAC-SHA256 is computed over ``"{ts}:{raw_body}"``.  Multiple ``h1`` values
    are supported (key rotation).  A timestamp outside *tolerance* is rejected
    to prevent replay of a captured payload.
    """
    if not secret or not signature_header:
        return False

    parts: dict[str, list[str]] = {}
    for chunk in signature_header.split(";"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        parts.setdefault(key.strip(), []).append(value.strip())

    try:
        timestamp = int(parts.get("ts", ["0"])[0])
    except (TypeError, ValueError):
        return False

    if tolerance and abs(time.time() - timestamp) > tolerance:
        return False

    signed_payload = f"{timestamp}:".encode() + raw_body
    expected = hmac.new(
        secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()

    return any(
        hmac.compare_digest(expected, candidate)
        for candidate in parts.get("h1", [])
    )


# ---------------------------------------------------------------------------
# Webhook state machine
# ---------------------------------------------------------------------------


def _parse_datetime(value: str | None):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt_timezone.utc)
    return parsed


def _resolve_plan(price_id: str | None) -> tuple[Plan | None, str | None]:
    """Map a provider price ID to (plan, billing_cycle)."""
    if not price_id:
        return None, None
    plan = Plan.objects.filter(
        Q(external_price_id_monthly=price_id)
        | Q(external_price_id_yearly=price_id),
        is_active=True,
    ).first()
    if plan is None:
        return None, None
    cycle = (
        Subscription.BillingCycle.YEARLY
        if plan.external_price_id_yearly == price_id
        else Subscription.BillingCycle.MONTHLY
    )
    return plan, cycle


def _find_subscription(data: dict, custom_data: dict) -> Subscription | None:
    provider_sub_id = data.get("id") if data.get("id") else data.get("subscription_id")
    if provider_sub_id:
        sub = Subscription.objects.filter(
            external_id=provider_sub_id,
            billing_provider="paddle",
        ).first()
        if sub:
            return sub

    user_id = (custom_data or {}).get("user_id")
    if user_id:
        sub = Subscription.objects.filter(user_id=user_id).first()
        if sub:
            return sub

    customer_id = data.get("customer_id")
    if customer_id:
        sub = Subscription.objects.filter(
            billing_metadata__customer_id=customer_id
        ).first()
        if sub:
            return sub
    return None


def _apply_subscription_payload(data: dict, event_type: str) -> dict:
    custom_data = data.get("custom_data") or {}
    sub = _find_subscription(data, custom_data)
    if sub is None:
        raise BillingProviderError(
            "Webhook does not match any local subscription "
            f"(user_id={custom_data.get('user_id')!r}, id={data.get('id')!r})."
        )

    items = data.get("items") or []
    price_id = None
    if items:
        price_id = ((items[0].get("price") or {}).get("id"))

    plan, cycle = _resolve_plan(price_id)
    if plan is None and price_id:
        # A paid event pointing at a price we do not know must never be
        # silently applied to the customer's current plan: fail loudly so the
        # price mapping is fixed (Paddle retries the webhook).
        raise BillingProviderError(
            f"Unknown price ID {price_id!r} — update Plan.external_price_id_*."
        )
    if plan is None:
        plan = sub.plan

    period = data.get("current_billing_period") or {}
    provider_status = data.get("status", "")
    new_status = STATUS_MAP.get(provider_status, sub.status)

    metadata = dict(sub.billing_metadata or {})
    metadata.update(
        {
            "customer_id": data.get("customer_id") or metadata.get("customer_id"),
            "price_id": price_id or metadata.get("price_id"),
            "provider_status": provider_status,
            "last_event_type": event_type,
            "environment": getattr(settings, "PADDLE_ENVIRONMENT", "sandbox"),
        }
    )

    with transaction.atomic():
        sub.plan = plan
        sub.status = new_status
        sub.billing_provider = "paddle"
        sub.external_id = data.get("id") or sub.external_id
        if cycle:
            sub.billing_cycle = cycle
        sub.current_period_start = _parse_datetime(
            period.get("starts_at")
        ) or sub.current_period_start
        sub.current_period_end = _parse_datetime(
            period.get("ends_at")
        ) or sub.current_period_end
        if new_status == Subscription.Status.CANCELLED:
            sub.cancelled_at = _parse_datetime(data.get("canceled_at")) or timezone.now()
        elif new_status in (Subscription.Status.ACTIVE, Subscription.Status.TRIALING):
            sub.cancelled_at = None
        sub.billing_metadata = metadata
        sub.save()

    logger.info(
        "Paddle webhook applied: user=%s tier=%s status=%s provider_status=%s",
        sub.user_id,
        sub.plan.tier,
        sub.status,
        provider_status,
    )
    return {
        "status": "applied",
        "user_id": sub.user_id,
        "plan": sub.plan.tier,
        "subscription_status": sub.status,
    }


def _apply_transaction_completed(data: dict) -> dict:
    """Fallback provisioning when ``subscription.created`` arrives late."""
    if data.get("status") not in (None, "completed"):
        return {"status": "ignored", "reason": "transaction not completed"}

    custom_data = data.get("custom_data") or {}
    items = data.get("items") or []
    price_id = (items[0] or {}).get("price_id") if items else None
    if not price_id and items:
        price_id = ((items[0].get("price") or {}).get("id"))

    sub = _find_subscription(
        {"subscription_id": data.get("subscription_id"), "customer_id": data.get("customer_id")},
        custom_data,
    )

    plan, cycle = _resolve_plan(price_id)
    if sub is None:
        user_id = custom_data.get("user_id")
        if not user_id:
            raise BillingProviderError(
                "Completed transaction has no custom_data.user_id."
            )
        sub = Subscription.objects.filter(user_id=user_id).first()
        if sub is None:
            raise BillingProviderError(
                f"Completed transaction references unknown user {user_id!r}."
            )
    if plan is None:
        raise BillingProviderError(
            f"Unknown price ID {price_id!r} — update Plan.external_price_id_*."
        )

    period = data.get("billing_period") or {}
    metadata = dict(sub.billing_metadata or {})
    metadata.update(
        {
            "customer_id": data.get("customer_id") or metadata.get("customer_id"),
            "price_id": price_id,
            "last_transaction_id": data.get("id"),
            "last_event_type": "transaction.completed",
            "environment": getattr(settings, "PADDLE_ENVIRONMENT", "sandbox"),
        }
    )

    with transaction.atomic():
        sub.plan = plan
        sub.status = Subscription.Status.ACTIVE
        sub.billing_provider = "paddle"
        sub.billing_cycle = cycle or sub.billing_cycle
        sub.external_id = data.get("subscription_id") or sub.external_id
        sub.current_period_start = _parse_datetime(
            period.get("starts_at")
        ) or sub.current_period_start
        sub.current_period_end = _parse_datetime(
            period.get("ends_at")
        ) or sub.current_period_end
        sub.cancelled_at = None
        sub.billing_metadata = metadata
        sub.save()

    logger.info(
        "Paddle transaction completed: user=%s tier=%s",
        sub.user_id,
        sub.plan.tier,
    )
    return {
        "status": "applied",
        "user_id": sub.user_id,
        "plan": sub.plan.tier,
        "subscription_status": sub.status,
    }


def process_paddle_event(event_type: str, data: dict) -> dict:
    """Apply a verified Paddle event to the local subscription."""
    if event_type.startswith("subscription."):
        return _apply_subscription_payload(data, event_type)
    if event_type == "transaction.completed":
        return _apply_transaction_completed(data)
    return {"status": "ignored", "event_type": event_type}
