from datetime import date, timedelta

from django.shortcuts import get_object_or_404
from rest_framework import filters, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.models import Report
from reports.serializers import ReportGenerateSerializer, ReportSerializer
from reports.tasks import generate_report
from websites.models import Website


class ReportListView(generics.ListAPIView):
    """GET /api/v1/reports/"""
    serializer_class   = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ["period_start", "current_score"]
    ordering           = ["-period_start"]

    def get_queryset(self):
        qs = Report.objects.filter(user=self.request.user).select_related("website")
        if website_id := self.request.query_params.get("website_id"):
            qs = qs.filter(website_id=website_id)
        if period := self.request.query_params.get("period"):
            qs = qs.filter(period=period)
        return qs


class ReportDetailView(generics.RetrieveAPIView):
    """GET /api/v1/reports/<id>/"""
    serializer_class   = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Report.objects.filter(user=self.request.user)


class GenerateReportView(APIView):
    """POST /api/v1/reports/generate/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request) -> Response:
        serializer = ReportGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        website = get_object_or_404(Website, pk=data["website_id"], owner=request.user)

        period_start = data["period_start"]
        period       = data.get("period", Report.Period.MONTHLY)

        # Compute period_end
        if period == Report.Period.MONTHLY:
            if period_start.month == 12:
                period_end = period_start.replace(year=period_start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                period_end = period_start.replace(month=period_start.month + 1, day=1) - timedelta(days=1)
        else:
            period_end = period_start + timedelta(days=6)

        report, created = Report.objects.get_or_create(
            website=website,
            period=period,
            period_start=period_start,
            defaults={
                "user":       request.user,
                "period_end": period_end,
                "status":     Report.Status.PENDING,
            },
        )

        if created or report.status == Report.Status.FAILED:
            generate_report.delay(str(report.id))

        return Response(
            ReportSerializer(report).data,
            status=status.HTTP_202_ACCEPTED,
        )
