from django.contrib import admin

from monitoring.models import MonitoringConfig


@admin.register(MonitoringConfig)
class MonitoringConfigAdmin(admin.ModelAdmin):
    list_display = ["website", "enabled", "interval", "next_scan_at", "consecutive_failures"]
    list_filter = ["enabled", "interval"]
    search_fields = ["website__domain"]
    readonly_fields = ["last_scan_at", "next_scan_at", "consecutive_failures", "escalation_level"]
