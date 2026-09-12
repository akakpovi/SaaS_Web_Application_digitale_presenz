from rest_framework import serializers
from subscriptions.models import Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Plan
        fields = [
            "id", "tier", "name", "description",
            "price_monthly", "price_yearly",
            "max_websites", "max_scans_per_month", "min_scan_interval",
            "can_export_reports", "can_use_api", "can_add_team_members",
            "max_team_members", "max_alert_channels",
            "features", "is_active",
        ]
        read_only_fields = fields


class SubscriptionSerializer(serializers.ModelSerializer):
    plan        = PlanSerializer(read_only=True)
    plan_tier   = serializers.CharField(source="plan.tier", read_only=True)
    is_active   = serializers.BooleanField(read_only=True)
    is_free     = serializers.BooleanField(read_only=True)

    class Meta:
        model  = Subscription
        fields = [
            "id", "plan", "plan_tier", "status", "billing_cycle",
            "started_at", "current_period_start", "current_period_end",
            "cancelled_at", "trial_end", "is_active", "is_free",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class UpgradeSubscriptionSerializer(serializers.Serializer):
    plan_tier     = serializers.ChoiceField(choices=Plan.Tier.choices)
    billing_cycle = serializers.ChoiceField(
        choices=Subscription.BillingCycle.choices,
        default=Subscription.BillingCycle.MONTHLY,
    )
