from django.contrib import admin

from notifications.models import NotificationChannel


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "channel_type", "enabled"]
    list_filter = ["channel_type", "enabled"]
    search_fields = ["name", "user__email"]
