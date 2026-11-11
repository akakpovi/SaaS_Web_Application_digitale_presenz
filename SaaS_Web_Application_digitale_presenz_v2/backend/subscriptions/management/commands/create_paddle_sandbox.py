"""Provisionne Paddle Sandbox depuis le catalogue de prix local.

Ce que la commande fait, de façon idempotente :

1. crée un produit Paddle par offre payante (Pro, Business, Agency) ;
2. crée les prix mensuel et annuel en EUR alignés sur ``subscriptions.pricing``
   et écrit les ``price_id`` dans ``Plan.external_price_id_*`` ;
3. optionnellement, crée la destination de webhook et écrit son secret dans un
   fichier 0600 (jamais dans la sortie standard).

Aucun montant n'est codé en dur : la source de vérité reste le catalogue et les
prix en base.

Usage :

    PADDLE_API_KEY=pdl_sdbx_... python manage.py create_paddle_sandbox \
        --webhook-url https://<tunnel>/api/v1/webhooks/paddle/

Garde-fous :
- refuse une URL d'API non-sandbox sans ``--allow-live`` ;
- refuse de créer quoi que ce soit sans clé API ;
- ne réécrit jamais un prix existant : un prix Paddle est immuable, il est
  réutilisé s'il correspond exactement (produit, montant, devise, cycle).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from subscriptions.models import Plan


class PaddleApiError(CommandError):
    pass


class Command(BaseCommand):
    help = "Create Paddle products/prices for the paid plans and map their price IDs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--webhook-url",
            default=os.environ.get("PADDLE_WEBHOOK_URL", ""),
            help="Public HTTPS URL of /api/v1/webhooks/paddle/",
        )
        parser.add_argument(
            "--secret-file",
            default=".paddle_webhook_secret",
            help="Where to write the webhook secret (0600). Never printed.",
        )
        parser.add_argument(
            "--allow-live",
            action="store_true",
            help="Required to touch a non-sandbox Paddle account.",
        )
        parser.add_argument(
            "--skip-products",
            action="store_true",
            help="Only create the webhook destination (prices already mapped).",
        )

    # ------------------------------------------------------------------ HTTP

    def _request(
        self, method: str, path: str, payload: dict | None = None, params=None
    ) -> dict:
        base = (settings.PADDLE_API_URL or "https://sandbox-api.paddle.com").rstrip("/")
        url = f"{base}{path}"
        try:
            response = requests.request(
                method,
                url,
                json=payload,
                params=params,
                headers={
                    "Authorization": f"Bearer {settings.PADDLE_API_KEY}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=20,
            )
        except requests.RequestException as exc:
            raise PaddleApiError(f"Paddle unreachable: {exc}") from exc

        if response.status_code >= 400:
            raise PaddleApiError(
                f"Paddle API {method} {path} -> HTTP {response.status_code}: "
                f"{response.text[:600]}"
            )
        try:
            return response.json().get("data") or {}
        except ValueError as exc:
            raise PaddleApiError("Paddle returned invalid JSON.") from exc

    def _list(self, path: str, params: dict | None = None) -> list[dict]:
        data = self._request("GET", path, params=params)
        # List endpoints return a list; Paddle wraps it in ``data``.
        return data if isinstance(data, list) else data.get("data") or []

    # --------------------------------------------------------------- products

    def _ensure_product(self, plan: Plan) -> str:
        name = f"Presence {plan.name}"
        for product in self._list("/products", {"status": "active", "per_page": 200}):
            if product.get("name") == name:
                self.stdout.write(f"  product {plan.name}: {product['id']} (existing)")
                return product["id"]

        created = self._request(
            "POST",
            "/products",
            {
                "name": name,
                "description": plan.description,
                "tax_category": "saas",
            },
        )
        product_id = created.get("id")
        if not product_id:
            raise PaddleApiError(f"Paddle returned no product ID for {plan.name}.")
        self.stdout.write(f"  product {plan.name}: {product_id} (created)")
        return product_id

    # ------------------------------------------------------------------ prices

    def _ensure_price(
        self,
        plan: Plan,
        product_id: str,
        cycle: str,
        amount: str,
    ) -> str:
        interval = "month" if cycle == "monthly" else "year"
        amount_cents = str(int(round(float(amount) * 100)))

        for price in self._list(
            "/prices", {"product_id": product_id, "status": "active", "per_page": 200}
        ):
            unit_price = price.get("unit_price") or {}
            billing_cycle = price.get("billing_cycle") or {}
            if (
                unit_price.get("amount") == amount_cents
                and unit_price.get("currency_code") == "EUR"
                and billing_cycle.get("interval") == interval
                and billing_cycle.get("frequency") == 1
            ):
                self.stdout.write(
                    f"  price {plan.name}/{cycle}: {price['id']} (existing)"
                )
                return price["id"]

        created = self._request(
            "POST",
            "/prices",
            {
                "product_id": product_id,
                "description": f"Presence {plan.name} — {cycle}",
                "unit_price": {"amount": amount_cents, "currency_code": "EUR"},
                "billing_cycle": {"interval": interval, "frequency": 1},
                "quantity": {"minimum": 1, "maximum": 1},
                "tax_mode": "account_setting",
            },
        )
        price_id = created.get("id")
        if not price_id:
            raise PaddleApiError(
                f"Paddle returned no price ID for {plan.name}/{cycle}."
            )
        self.stdout.write(f"  price {plan.name}/{cycle}: {price_id} (created)")
        return price_id

    # ----------------------------------------------------------------- webhook

    def _ensure_webhook(self, url: str, secret_file: Path) -> None:
        if not url.startswith("https://"):
            raise CommandError(
                "The webhook URL must be HTTPS: Paddle rejects HTTP destinations."
            )
        for setting in self._list("/notification-settings", {"per_page": 200}):
            if setting.get("destination") == url:
                self.stdout.write(
                    f"  webhook: already exists (id={setting.get('id')}) — "
                    "its secret cannot be read back; rotate it in Paddle if lost"
                )
                return

        created = self._request(
            "POST",
            "/notification-settings",
            {
                "description": "Presence — subscription lifecycle",
                "type": "url",
                "destination": url,
                "subscribed_events": [
                    "subscription.created",
                    "subscription.updated",
                    "subscription.canceled",
                    "transaction.completed",
                ],
            },
        )
        secret = created.get("endpoint_secret_key") or ""
        if not secret:
            raise PaddleApiError(
                "Webhook created but Paddle returned no endpoint_secret_key."
            )
        secret_file.write_text(secret + "\n", encoding="utf-8")
        secret_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        self.stdout.write(
            f"  webhook: created (id={created.get('id')}); secret written to "
            f"{secret_file} (0600) — copy it to PADDLE_WEBHOOK_SECRET"
        )

    # -------------------------------------------------------------------- run

    def handle(self, *args, **options):
        if not settings.PADDLE_API_KEY:
            raise CommandError(
                "PADDLE_API_KEY is empty. Create a Sandbox API key in Paddle "
                "(Developer tools → Authentication) and put it in backend/.env."
            )
        api_url = (settings.PADDLE_API_URL or "").lower()
        if "sandbox" not in api_url and not options["allow_live"]:
            raise CommandError(
                f"Refusing to modify {settings.PADDLE_API_URL!r} without --allow-live."
            )

        plans = Plan.objects.filter(
            tier__in=[Plan.Tier.PRO, Plan.Tier.BUSINESS, Plan.Tier.AGENCY]
        )
        if not plans.exists():
            raise CommandError(
                "No paid plan found. Run `manage.py create_plans` first."
            )

        self.stdout.write(
            f"Paddle environment: {settings.PADDLE_ENVIRONMENT} ({settings.PADDLE_API_URL})"
        )

        if not options["skip_products"]:
            for plan in plans.order_by("price_monthly"):
                product_id = self._ensure_product(plan)
                plan.external_price_id_monthly = self._ensure_price(
                    plan, product_id, "monthly", plan.price_monthly
                )
                plan.external_price_id_yearly = self._ensure_price(
                    plan, product_id, "yearly", plan.price_yearly
                )
                plan.save(
                    update_fields=[
                        "external_price_id_monthly",
                        "external_price_id_yearly",
                    ]
                )

        webhook_url = (options["webhook_url"] or "").strip()
        if webhook_url:
            secret_file = Path(options["secret_file"])
            if not secret_file.is_absolute():
                secret_file = Path(settings.BASE_DIR) / secret_file
            secret_file.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_webhook(webhook_url, secret_file)

        self.stdout.write(self.style.SUCCESS("Paddle Sandbox provisioning complete."))
        self.stdout.write(
            "Next: BILLING_ENABLED=true, PADDLE_WEBHOOK_SECRET=<secret>, then "
            "restart web and complete a Sandbox checkout."
        )
