"""Serializers for the public website checker."""

from rest_framework import serializers

from core.security import (
    DomainValidationError,
    validate_domain_for_scan,
)


class PublicScanRequestSerializer(serializers.Serializer):
    """Validate and normalize a public website scan request."""

    domain = serializers.CharField(
        max_length=253,
        trim_whitespace=True,
    )

    def validate_domain(self, value: str) -> str:
        try:
            # Must normalize the domain AND perform SSRF validation
            # before any Celery task is enqueued.
            return validate_domain_for_scan(value)

        except DomainValidationError as exc:
            raise serializers.ValidationError(
                "The supplied domain is invalid or not allowed."
            ) from exc


class PublicCheckResultSerializer(serializers.Serializer):
    """Result returned by one website-health scanner."""

    category = serializers.CharField()

    score = serializers.IntegerField(
        min_value=0,
        max_value=100,
        allow_null=True,
    )

    max_score = serializers.IntegerField(
        read_only=True,
        allow_null=True,
    )

    status = serializers.ChoiceField(
        choices=(
            "healthy",
            "warning",
            "critical",
            "neutral",
        )
    )

    message = serializers.CharField()

    details = serializers.DictField(
        required=False,
        default=dict,
    )

    recommendation = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class PublicScanStateSerializer(serializers.Serializer):
    """Current state or completed result of a public scan."""

    scan_id = serializers.CharField()

    # Transitional compatibility with the previous frontend/API shape.
    id = serializers.CharField(
        required=False,
    )

    domain = serializers.CharField()

    status = serializers.ChoiceField(
        choices=(
            "queued",
            "processing",
            "completed",
            "partial",
            "failed",
        )
    )

    progress = serializers.IntegerField(
        min_value=0,
        max_value=100,
        required=False,
        default=0,
    )

    health_score = serializers.IntegerField(
        min_value=0,
        max_value=100,
        allow_null=True,
        required=False,
    )

    health_status = serializers.ChoiceField(
        choices=(
            "healthy",
            "warning",
            "critical",
            "neutral",
        ),
        allow_null=True,
        required=False,
    )

    scanned_at = serializers.DateTimeField(
        required=False,
    )

    checks = PublicCheckResultSerializer(
        many=True,
        required=False,
        default=list,
    )

    poll_url = serializers.CharField(
        required=False,
    )
