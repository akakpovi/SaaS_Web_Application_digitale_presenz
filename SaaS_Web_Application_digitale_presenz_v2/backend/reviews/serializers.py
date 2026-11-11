from rest_framework import serializers
from reviews.models import (
    ResponseDraft,
    Review,
    ReviewSource,
    ReviewSentiment,
    ReviewImportJob,
)


class ReviewSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewSource
        fields = "__all__"
        read_only_fields = ["id", "user", "last_synced_at", "created_at", "updated_at"]


class ReviewSerializer(serializers.ModelSerializer):
    source_provider = serializers.CharField(source="source.provider", read_only=True)
    source_name = serializers.CharField(source="source.name", read_only=True)
    response_status = serializers.SerializerMethodField()
    response_draft_id = serializers.SerializerMethodField()
    response_draft_content = serializers.SerializerMethodField()
    has_response = serializers.SerializerMethodField()
    needs_response = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id",
            "source_id",
            "source_provider",
            "source_name",
            "external_id",
            "author_name",
            "author_photo",
            "rating",
            "text",
            "sentiment",
            "language",
            "is_approved",
            "review_date",
            "created_at",
            "updated_at",
            "response_status",
            "response_draft_id",
            "response_draft_content",
            "has_response",
            "needs_response",
        ]
        read_only_fields = [
            "id",
            "source_id",
            "source_provider",
            "source_name",
            "external_id",
            "created_at",
            "updated_at",
            "response_status",
            "response_draft_id",
            "response_draft_content",
            "has_response",
            "needs_response",
        ]

    @staticmethod
    def _draft(review: Review):
        # ``response_draft`` is a reverse OneToOne: accessing it on a review
        # without a draft raises RelatedObjectDoesNotExist, not None.
        return getattr(review, "response_draft", None)

    def get_response_status(self, review: Review) -> str | None:
        draft = self._draft(review)
        return draft.status if draft else None

    def get_response_draft_id(self, review: Review) -> int | None:
        draft = self._draft(review)
        return draft.id if draft else None

    def get_response_draft_content(self, review: Review) -> str:
        draft = self._draft(review)
        return draft.content if draft else ""

    def get_has_response(self, review: Review) -> bool:
        return self._draft(review) is not None

    def get_needs_response(self, review: Review) -> bool:
        """A review needs an answer when it is negative/neutral and unanswered."""
        if self._draft(review) is not None:
            return False
        if review.sentiment in (Review.Sentiment.NEGATIVE, Review.Sentiment.NEUTRAL):
            return True
        return review.rating is not None and review.rating <= 3


class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = [
            "source",
            "author_name",
            "author_photo",
            "rating",
            "text",
            "sentiment",
            "language",
            "review_date",
            "is_approved",
        ]

    def validate_source(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError("You do not own this review source.")
        return value


class ResponseDraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResponseDraft
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
            "id",
            "source",
            "file",
            "file_type",
            "total_rows",
            "imported_count",
            "failed_count",
            "errors",
            "status",
            "created_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "total_rows",
            "imported_count",
            "failed_count",
            "errors",
            "status",
            "created_at",
            "completed_at",
        ]
