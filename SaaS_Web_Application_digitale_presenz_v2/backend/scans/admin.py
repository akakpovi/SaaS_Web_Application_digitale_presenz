from django.contrib import admin

from .models import CheckResult, Scan


class CheckResultInline(admin.TabularInline):
    model = CheckResult
    extra = 0
    readonly_fields = ("category", "status", "score", "summary", "created_at")
    fields = ("category", "status", "score", "summary", "created_at")


@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ("id", "website", "status", "trigger", "health_score", "health_status", "created_at")
    list_filter = ("status", "trigger", "health_status", "created_at")
    search_fields = ("website__domain",)
    readonly_fields = ("created_at", "updated_at", "started_at", "completed_at")
    raw_id_fields = ("website",)
    inlines = [CheckResultInline]


@admin.register(CheckResult)
class CheckResultAdmin(admin.ModelAdmin):
    list_display = ("id", "scan", "category", "status", "score", "created_at")
    list_filter = ("category", "status")
    search_fields = ("scan__website__domain",)
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("scan",)
