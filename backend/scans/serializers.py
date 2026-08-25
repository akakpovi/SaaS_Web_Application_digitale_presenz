from rest_framework import serializers

from .models import CheckResult, Scan
from .services.scoring import CHECK_WEIGHTS


class CheckResultSerializer(serializers.ModelSerializer[CheckResult]):
    max_score = serializers.SerializerMethodField()

    class Meta:
        model = CheckResult
        fields = (
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
        )
        read_only_fields = fields

    def get_max_score(self, instance: CheckResult) -> int | None:
        return CHECK_WEIGHTS.get(instance.category)


class ScanSerializer(serializers.ModelSerializer[Scan]):
    check_results = CheckResultSerializer(many=True, read_only=True)
    website_id = serializers.IntegerField(read_only=True)
    domain = serializers.CharField(source="website.domain", read_only=True)

    class Meta:
        model = Scan
        fields = (
            "id",
            "website_id",
            "domain",
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
        )
        read_only_fields = fields
