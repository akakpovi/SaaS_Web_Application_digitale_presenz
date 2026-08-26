from django.core.management.base import BaseCommand
from subscriptions.models import Plan


class Command(BaseCommand):
    help = "Create default subscription plans"

    def handle(self, *args, **options):
        plans = [
            {
                "tier": Plan.Tier.FREE,
                "name": "Free",
                "description": "Perfect for getting started",
                "price_monthly": 0,
                "price_yearly": 0,
                "max_websites": 1,
                "max_scans_per_month": 10,
                "min_scan_interval": "24h",
                "can_export_reports": False,
                "can_use_api": False,
                "can_add_team_members": False,
                "max_team_members": 1,
                "max_alert_channels": 1,
                "features": ["1 website", "10 scans/month", "Basic alerts", "Email notifications"],
            },
            {
                "tier": Plan.Tier.PRO,
                "name": "Pro",
                "description": "For professionals and small businesses",
                "price_monthly": 19,
                "price_yearly": 190,
                "max_websites": 10,
                "max_scans_per_month": 500,
                "min_scan_interval": "1h",
                "can_export_reports": True,
                "can_use_api": True,
                "can_add_team_members": False,
                "max_team_members": 1,
                "max_alert_channels": 5,
                "features": ["10 websites", "500 scans/month", "Hourly monitoring", "PDF reports", "API access", "Slack/Discord alerts"],
            },
            {
                "tier": Plan.Tier.BUSINESS,
                "name": "Business",
                "description": "For agencies and large teams",
                "price_monthly": 49,
                "price_yearly": 490,
                "max_websites": 50,
                "max_scans_per_month": 5000,
                "min_scan_interval": "5m",
                "can_export_reports": True,
                "can_use_api": True,
                "can_add_team_members": True,
                "max_team_members": 10,
                "max_alert_channels": 20,
                "features": ["50 websites", "5000 scans/month", "5-min monitoring", "Team access", "Priority support", "Custom webhooks"],
            },
        ]
        for plan_data in plans:
            obj, created = Plan.objects.update_or_create(
                tier=plan_data["tier"],
                defaults=plan_data,
            )
            status = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{status}: {obj}"))
