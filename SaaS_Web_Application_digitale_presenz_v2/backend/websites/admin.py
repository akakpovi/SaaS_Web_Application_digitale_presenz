from django.contrib import admin

from .models import Website


@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    list_display = ("domain", "owner", "display_name", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("domain", "display_name", "owner__email")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("owner",)
