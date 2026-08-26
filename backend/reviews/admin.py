from django.contrib import admin
from reviews.models import ResponseDraft, Review, ReviewSource


@admin.register(ReviewSource)
class ReviewSourceAdmin(admin.ModelAdmin):
    list_display  = ["website", "provider", "name", "enabled", "last_synced_at"]
    list_filter   = ["provider", "enabled"]
    search_fields = ["website__domain", "user__email"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display  = ["author_name", "source", "rating", "sentiment", "is_approved", "review_date"]
    list_filter   = ["is_approved", "sentiment"]
    search_fields = ["author_name", "text"]


@admin.register(ResponseDraft)
class ResponseDraftAdmin(admin.ModelAdmin):
    list_display  = ["review", "user", "status", "sent_at"]
    list_filter   = ["status"]
