from rest_framework import serializers
from reports.models import Report


class ReportSerializer(serializers.ModelSerializer):
    website_domain = serializers.CharField(source="website.domain", read_only=True)
    score_trend    = serializers.CharField(read_only=True)

    class Meta:
        model  = Report
        fields = [
            "id", "website_id", "website_domain",
            "period", "period_start", "period_end", "status",
            "current_score", "previous_score", "score_change", "score_trend",
            "check_breakdown", "improvements", "problems",
            "recommendations", "score_history",
            "total_scans", "generated_at", "created_at", "updated_at",
        ]
        read_only_fields = fields


class ReportGenerateSerializer(serializers.Serializer):
    website_id   = serializers.IntegerField()
    period       = serializers.ChoiceField(choices=Report.Period.choices, default=Report.Period.MONTHLY)
    period_start = serializers.DateField()
