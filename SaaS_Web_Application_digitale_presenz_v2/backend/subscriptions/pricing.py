"""Catalogue de référence des offres Presence.

Une seule source de vérité pour les prix, les quotas et les libellés.
``create_plans`` s'en sert pour alimenter la base, l'API la sert au frontend
et les tests de cohérence vérifient que les trois restent alignés.

Tarification retenue (Itération 4) :

===========  ==========  ===========
Offre        Mensuel     Annuel
===========  ==========  ===========
Free         0 €         0 €
Pro          9 €         90 €
Business     29 €        290 €
Agency       79 €        790 €
===========  ==========  ===========

L'annuel correspond à dix mois payés (deux mois offerts).
"""

from __future__ import annotations

from decimal import Decimal

#: Devise unique du catalogue (Paddle est configuré en EUR).
CURRENCY = "EUR"

PLAN_CATALOGUE: list[dict] = [
    {
        "tier": "free",
        "name": "Free",
        "description": "Get started with basic monitoring",
        "price_monthly": Decimal("0.00"),
        "price_yearly": Decimal("0.00"),
        "max_websites": 1,
        "max_scans_per_month": 10,
        "min_scan_interval": "24h",
        "can_export_reports": False,
        "can_use_api": False,
        "can_add_team_members": False,
        "max_team_members": 1,
        "max_alert_channels": 1,
        "features": [
            "1 website",
            "10 scans/month",
            "Basic alerts",
            "Email notifications",
        ],
    },
    {
        "tier": "pro",
        "name": "Pro",
        "description": "For professionals and small businesses",
        "price_monthly": Decimal("9.00"),
        "price_yearly": Decimal("90.00"),
        "max_websites": 10,
        "max_scans_per_month": 500,
        "min_scan_interval": "1h",
        "can_export_reports": True,
        "can_use_api": True,
        "can_add_team_members": False,
        "max_team_members": 1,
        "max_alert_channels": 5,
        "features": [
            "10 websites",
            "500 scans/month",
            "Hourly monitoring",
            "PDF reports",
            "API access",
            "Slack/Discord alerts",
        ],
    },
    {
        "tier": "business",
        "name": "Business",
        "description": "For growing teams and multi-site businesses",
        "price_monthly": Decimal("29.00"),
        "price_yearly": Decimal("290.00"),
        "max_websites": 50,
        "max_scans_per_month": 5000,
        "min_scan_interval": "5m",
        "can_export_reports": True,
        "can_use_api": True,
        "can_add_team_members": True,
        "max_team_members": 5,
        "max_alert_channels": 10,
        "features": [
            "50 websites",
            "5000 scans/month",
            "5-min monitoring",
            "Team access",
            "Priority support",
            "Custom webhooks",
        ],
    },
    {
        "tier": "agency",
        "name": "Agency",
        "description": "For agencies managing many client websites",
        "price_monthly": Decimal("79.00"),
        "price_yearly": Decimal("790.00"),
        "max_websites": 200,
        "max_scans_per_month": 20000,
        "min_scan_interval": "5m",
        "can_export_reports": True,
        "can_use_api": True,
        "can_add_team_members": True,
        "max_team_members": 20,
        "max_alert_channels": 25,
        "features": [
            "200 websites",
            "20000 scans/month",
            "5-min monitoring",
            "White-label PDF reports",
            "Team access (20 seats)",
            "Priority support",
        ],
    },
]

#: Index par tier, pratique pour les tests et les messages d'erreur.
CATALOGUE_BY_TIER: dict[str, dict] = {p["tier"]: p for p in PLAN_CATALOGUE}

PAID_TIERS = tuple(t for t in CATALOGUE_BY_TIER if t != "free")


def get_catalogue_entry(tier: str) -> dict:
    try:
        return CATALOGUE_BY_TIER[tier]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unknown plan tier: {tier!r}") from exc
