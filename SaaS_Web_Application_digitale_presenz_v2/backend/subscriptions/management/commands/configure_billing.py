"""Associe les price_id Paddle aux offres, sans toucher au code.

Usage (après avoir créé les prix dans Paddle) :

    PADDLE_PRICE_PRO_MONTHLY=pri_... \\
    PADDLE_PRICE_PRO_YEARLY=pri_... \\
    ... python manage.py configure_billing

Les price_id restent en base (``Plan.external_price_id_*``) : le checkout ne
lit jamais un montant envoyé par le client, seulement ce mapping.
"""

import os

from django.core.management.base import BaseCommand

from subscriptions.models import Plan

ENV_MAP = {
    Plan.Tier.PRO: ("PADDLE_PRICE_PRO_MONTHLY", "PADDLE_PRICE_PRO_YEARLY"),
    Plan.Tier.BUSINESS: (
        "PADDLE_PRICE_BUSINESS_MONTHLY",
        "PADDLE_PRICE_BUSINESS_YEARLY",
    ),
    Plan.Tier.AGENCY: ("PADDLE_PRICE_AGENCY_MONTHLY", "PADDLE_PRICE_AGENCY_YEARLY"),
}


class Command(BaseCommand):
    help = "Set Plan.external_price_id_* from PADDLE_PRICE_* environment variables"

    def handle(self, *args, **options):
        updated = 0
        missing: list[str] = []

        for tier, (monthly_var, yearly_var) in ENV_MAP.items():
            plan = Plan.objects.filter(tier=tier).first()
            if plan is None:
                missing.append(f"plan {tier}")
                continue

            monthly = os.environ.get(monthly_var, "").strip()
            yearly = os.environ.get(yearly_var, "").strip()

            if monthly:
                plan.external_price_id_monthly = monthly
            if yearly:
                plan.external_price_id_yearly = yearly
            if monthly or yearly:
                plan.save(
                    update_fields=[
                        "external_price_id_monthly",
                        "external_price_id_yearly",
                    ]
                )
                updated += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{plan.name}: monthly={plan.external_price_id_monthly or '—'} "
                        f"yearly={plan.external_price_id_yearly or '—'}"
                    )
                )
            else:
                missing.append(f"{monthly_var}/{yearly_var}")

        if updated == 0:
            self.stdout.write(
                self.style.WARNING(
                    "Aucun price_id fourni. Définissez PADDLE_PRICE_* puis relancez."
                )
            )
            return

        if missing:
            self.stdout.write(
                self.style.WARNING("Non configuré : " + ", ".join(missing))
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"{updated} offre(s) mises à jour. "
                "Le webhook doit pointer vers /api/v1/webhooks/paddle/."
            )
        )
