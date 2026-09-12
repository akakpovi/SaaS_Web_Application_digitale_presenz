from rest_framework import serializers
from reviews.models import ResponseDraft, Review, ReviewSource, ReviewSentiment, ReviewImportJob

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

class ReviewSentimentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewSentiment
        fields = "__all__"

class ReviewImportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewImportJob
        fields = [
            "id", "source", "file", "file_type", "total_rows",
            "imported_count", "failed_count", "errors", "status",
            "created_at", "completed_at"
        ]
        read_only_fields = ["id", "total_rows", "imported_count", "failed_count", "errors", "status", "created_at", "completed_at"]
