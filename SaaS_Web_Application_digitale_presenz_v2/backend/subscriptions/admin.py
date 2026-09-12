from django.contrib import admin
from subscriptions.models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display  = ["tier", "name", "price_monthly", "max_websites", "is_active"]
    list_filter   = ["is_active", "tier"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display  = ["user", "plan", "status", "billing_cycle", "started_at"]
    list_filter   = ["status", "billing_cycle", "plan__tier"]
    search_fields = ["user__email"]
    readonly_fields = ["id", "created_at", "updated_at"]
