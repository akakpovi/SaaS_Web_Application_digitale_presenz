from django.contrib import admin
from reports.models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display  = ["website", "period", "period_start", "status", "current_score", "score_change"]
    list_filter   = ["status", "period"]
    search_fields = ["website__domain", "user__email"]
    readonly_fields = ["id", "generated_at", "created_at", "updated_at"]
