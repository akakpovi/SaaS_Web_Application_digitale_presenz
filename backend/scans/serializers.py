from rest_framework import serializers
from .models import Scan, CheckResult


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

    def get_max_score(self, obj):
        return 20


class ScanSerializer(serializers.ModelSerializer):
    domain = serializers.CharField(source="website.domain", read_only=True)
    website_id = serializers.IntegerField(source="website.id", read_only=True)
    check_results = CheckResultSerializer(many=True, read_only=True)

    class Meta:
        model = Scan
        fields = [
            "id",
            "domain",
            "website_id",
            "status",
            "health_score",
            "health_status",
            "trigger",
            "failure_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
            "check_results",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
