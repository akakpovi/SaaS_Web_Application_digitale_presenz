from django.contrib import admin

from alerts.models import Alert, AlertPreference, AlertRule, MuteWindow


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ["title", "website", "alert_type", "severity", "status", "created_at"]
    list_filter = ["status", "severity", "alert_type"]
    search_fields = ["title", "website__domain", "user__email"]
    readonly_fields = ["id", "acknowledged_at", "resolved_at", "created_at", "updated_at"]


@admin.register(AlertPreference)
class AlertPreferenceAdmin(admin.ModelAdmin):
    list_display = ["user", "digest_frequency", "ssl_expiry_warning_days"]
    search_fields = ["user__email"]


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "metric", "operator", "threshold", "severity", "enabled"]
    list_filter = ["enabled", "severity", "metric"]


@admin.register(MuteWindow)
class MuteWindowAdmin(admin.ModelAdmin):
    list_display = ["user", "start_at", "end_at", "reason", "is_active"]
    list_filter = ["is_active", "reason"]
