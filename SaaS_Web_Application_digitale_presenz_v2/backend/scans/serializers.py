"""Scans application serializers.

Backward compatibility: ``ScanSerializer`` and ``CheckResultSerializer``
keep all existing fields.  New fields are additive.
"""

from __future__ import annotations

from rest_framework import serializers

from .models import CheckResult, Finding, Scan, ScannerRun


class CheckResultSerializer(serializers.ModelSerializer):
    max_score = serializers.SerializerMethodField()

    class Meta:
        model = CheckResult
        fields = [
            "id",
            "category",
            "status",
            "score",
            "max_score",
            "summary",
            "recommendation",
            "technical_details",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_max_score(self, obj: CheckResult) -> int:
        from scans.services.scoring import CHECK_WEIGHTS

        return CHECK_WEIGHTS.get(obj.category, 20)


class ScanSerializer(serializers.ModelSerializer):
    """Full scan serializer — includes new scanner engine fields."""

    domain = serializers.CharField(source="website.domain", read_only=True)
    website_id = serializers.IntegerField(source="website.id", read_only=True)
    check_results = CheckResultSerializer(many=True, read_only=True)
    duration_seconds = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Scan
        fields = [
            # --- existing fields (preserved) ---
            "id",
            "domain",
            "website_id",
            "status",
            "trigger",
            "health_score",
            "health_status",
            "failure_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
            "check_results",
            # --- new fields ---
            "scan_type",
            "progress",
            "current_step",
            "steps",
            "queued_at",
            "failed_at",
            "duration_seconds",
            "is_active",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_duration_seconds(self, obj: Scan) -> int | None:
        return obj.duration_seconds


class ScanListSerializer(serializers.ModelSerializer):
    """Lightweight list serializer — no nested check_results."""

    domain = serializers.CharField(source="website.domain", read_only=True)
    website_id = serializers.IntegerField(source="website.id", read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = Scan
        fields = [
            "id",
            "domain",
            "website_id",
            "status",
            "trigger",
            "scan_type",
            "health_score",
            "health_status",
            "progress",
            "current_step",
            "started_at",
            "completed_at",
            "created_at",
            "is_active",
            "duration_seconds",
        ]

    def get_duration_seconds(self, obj: Scan) -> int | None:
        return obj.duration_seconds


class ScannerRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScannerRun
        fields = [
            "id",
            "scanner",
            "status",
            "started_at",
            "finished_at",
            "duration_ms",
            "exit_code",
            "error_message",
            "metadata",
            "created_at",
            # raw_output is intentionally excluded from API responses
        ]
        read_only_fields = fields


class FindingSerializer(serializers.ModelSerializer):
    scanner = serializers.CharField(source="scanner_run.scanner", read_only=True)

    class Meta:
        model = Finding
        fields = [
            "id",
            "scanner",
            "category",
            "check_code",
            "title",
            "description",
            "severity",
            "status",
            "evidence",
            "detected_value",
            "expected_value",
            "recommendation",
            "reference_url",
            "duration_ms",
            "created_at",
        ]
        read_only_fields = fields
