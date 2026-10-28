#!/usr/bin/env python3
"""Vérifie que le catalogue backend et le miroir frontend sont identiques.

Trois sources de prix avaient divergé (base, /pricing, /billing) lors de
l'audit.  Ce garde-fou casse la CI dès qu'un prix, une limite ou une
fonctionnalité diffère entre ``subscriptions/pricing.py`` et
``src/data/plans.json`` (utilisé par le pré-rendu SEO et le repli hors ligne).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRICING_PY = (
    ROOT
    / "SaaS_Web_Application_digitale_presenz_v2"
    / "backend"
    / "subscriptions"
    / "pricing.py"
)
PLANS_JSON = (
    ROOT
    / "SaaS_Web_Application_digitale_presenz_v2"
    / "SaaS_Web_Application_UI_UX_frontendV2"
    / "src"
    / "data"
    / "plans.json"
)

FIELDS = [
    "name",
    "description",
    "max_websites",
    "max_scans_per_month",
    "max_alert_channels",
    "can_export_reports",
    "can_use_api",
    "features",
]


def load_catalogue() -> list[dict]:
    spec = importlib.util.spec_from_file_location("presence_pricing", PRICING_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return [
        {
            **entry,
            "price_monthly": float(entry["price_monthly"]),
            "price_yearly": float(entry["price_yearly"]),
        }
        for entry in module.PLAN_CATALOGUE
    ]


def main() -> int:
    backend = {plan["tier"]: plan for plan in load_catalogue()}
    frontend = {plan["tier"]: plan for plan in json.loads(PLANS_JSON.read_text())["plans"]}

    errors: list[str] = []

    if set(backend) != set(frontend):
        errors.append(
            f"Tiers differ: backend={sorted(backend)} frontend={sorted(frontend)}"
        )

    for tier in sorted(set(backend) & set(frontend)):
        for field in FIELDS + ["price_monthly", "price_yearly"]:
            if backend[tier][field] != frontend[tier][field]:
                errors.append(
                    f"{tier}.{field}: backend={backend[tier][field]!r} "
                    f"frontend={frontend[tier][field]!r}"
                )

    if errors:
        print("Pricing catalogue is out of sync:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    prices = ", ".join(
        f"{tier}={backend[tier]['price_monthly']:g}€"
        for tier in sorted(backend)
    )
    print(f"OK — pricing in sync ({prices}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
