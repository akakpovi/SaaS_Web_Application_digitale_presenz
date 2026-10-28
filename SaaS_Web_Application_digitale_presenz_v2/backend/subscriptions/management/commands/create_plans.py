from django.core.management.base import BaseCommand

from subscriptions.models import Plan
from subscriptions.pricing import PLAN_CATALOGUE


class Command(BaseCommand):
    help = "Create or update the subscription plans from subscriptions.pricing"

    def handle(self, *args, **options):
        for entry in PLAN_CATALOGUE:
            data = dict(entry)
            data["tier"] = Plan.Tier(data["tier"])
            obj, created = Plan.objects.update_or_create(
                tier=data["tier"],
                defaults=data,
            )
            status = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{status}: {obj.name} — {obj.price_monthly} €/mo "
                    f"({obj.price_yearly} €/yr)"
                )
            )
