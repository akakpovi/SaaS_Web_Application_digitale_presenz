from rest_framework import serializers
from reports.models import Report


class ReportSerializer(serializers.ModelSerializer):
    website_domain = serializers.CharField(source="website.domain", read_only=True)
    score_trend = serializers.CharField(read_only=True)
    latest_scan_id = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            "id",
            "website_id",
            "website_domain",
            "period",
            "period_start",
            "period_end",
            "status",
            "current_score",
            "previous_score",
            "score_change",
            "score_trend",
            "check_breakdown",
            "improvements",
            "problems",
            "recommendations",
            "score_history",
            "total_scans",
            "generated_at",
            "created_at",
            "updated_at",
            "latest_scan_id",
        ]
        read_only_fields = fields

    def get_latest_scan_id(self, report: Report) -> int | None:
        """Scan used by the white-label PDF endpoint for this period."""
        from scans.models import Scan

        return (
            Scan.objects.filter(
                website=report.website,
                status=Scan.Status.COMPLETED,
                created_at__date__gte=report.period_start,
                created_at__date__lte=report.period_end,
            )
            .order_by("-created_at")
            .values_list("id", flat=True)
            .first()
        )


class ReportGenerateSerializer(serializers.Serializer):
    website_id = serializers.IntegerField()
    period = serializers.ChoiceField(
        choices=Report.Period.choices, default=Report.Period.MONTHLY
    )
    period_start = serializers.DateField()
