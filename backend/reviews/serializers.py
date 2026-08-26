from rest_framework import serializers
from reviews.models import ResponseDraft, Review, ReviewSource


class ReviewSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ReviewSource
        fields = "__all__"
        read_only_fields = ["id", "user", "last_synced_at", "created_at", "updated_at"]


class ReviewSerializer(serializers.ModelSerializer):
    source_provider = serializers.CharField(source="source.provider", read_only=True)
    source_name     = serializers.CharField(source="source.name",     read_only=True)

    class Meta:
        model  = Review
        fields = [
            "id", "source_id", "source_provider", "source_name",
            "external_id", "author_name", "author_photo",
            "rating", "text", "sentiment", "language",
            "is_approved", "review_date", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "source_id", "source_provider", "source_name",
            "external_id", "created_at", "updated_at",
        ]


class ReviewCreateSerializer(serializers.ModelSerializer):
    """For manually creating reviews."""
    class Meta:
        model  = Review
        fields = [
            "source", "author_name", "author_photo",
            "rating", "text", "sentiment", "language",
            "review_date", "is_approved",
        ]

    def validate_source(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError("You do not own this review source.")
        return value


class ResponseDraftSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ResponseDraft
        fields = "__all__"
        read_only_fields = ["id", "user", "sent_at", "created_at", "updated_at"]
