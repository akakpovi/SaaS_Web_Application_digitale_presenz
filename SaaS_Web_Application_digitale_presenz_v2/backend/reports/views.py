import logging
from datetime import datetime
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from reports.models import Report
from reports.serializers import ReportGenerateSerializer, ReportSerializer
from reports.services import ensure_monthly_reports, generate_report_data, month_bounds
from scans.models import Scan, HealthStatus
from websites.models import Website

logger = logging.getLogger(__name__)


class WhiteLabelPDFReportView(APIView):
    """
    GET /api/v1/reports/pdf/<scan_id>/
    Génération PDF Marque Blanche avec WeasyPrint.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, scan_id: int):
        from subscriptions.services.quotas import assert_feature

        assert_feature(request.user, "can_export_reports")
        try:
            scan = (
                Scan.objects
                .select_related("website")
                .prefetch_related("check_results")
                .get(pk=scan_id)
            )
        except (Scan.DoesNotExist, ValueError):
            return Response({"detail": "Scan introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if scan.website.owner and scan.website.owner != request.user:
            return Response({"detail": "Accès non autorisé à ce rapport."}, status=status.HTTP_403_FORBIDDEN)

        logo_url = request.query_params.get("logo_url", "")
        lang = request.query_params.get("lang", "fr")

        checks = scan.check_results.all()
        critical_count = sum(1 for c in checks if c.status == HealthStatus.CRITICAL.value)
        warning_count = sum(1 for c in checks if c.status == HealthStatus.WARNING.value)
        passed_count = sum(1 for c in checks if c.status in [HealthStatus.HEALTHY.value, "passed"])

        score = scan.health_score or 0
        score_color = "#16a34a" if score >= 80 else ("#d97706" if score >= 50 else "#dc2626")

        context = {
            "domain": scan.website.domain,
            "score": score,
            "score_color": score_color,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "passed_count": passed_count,
            "checks": [
                {
                    "category": c.category.replace("_", " ").title(),
                    "status": c.status,
                    "score": c.score or 0,
                    "summary": c.summary,
                }
                for c in checks
            ],
            "logo_url": logo_url,
            "language": lang,
            "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }

        html_string = render_to_string("reports/white_label_report.html", context)

        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html_string).write_pdf()
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            filename = f"rapport-presence-{scan.website.domain}-{scan.id}.pdf"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            logger.warning(f"WeasyPrint fallback HTML: {e}")
            response = HttpResponse(html_string, content_type="text/html")
            return response


class GenerateReportView(APIView):
    """POST /api/v1/reports/generate/ — persist a real report from stored scans."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from subscriptions.services.quotas import assert_feature

        assert_feature(request.user, "can_export_reports")
        serializer = ReportGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        website = Website.objects.filter(
            id=data["website_id"], owner=request.user
        ).first()
        if not website:
            return Response(
                {"detail": "Site introuvable ou non autorisé."},
                status=status.HTTP_404_NOT_FOUND,
            )

        period_start = data["period_start"]
        period_end = (
            month_bounds(period_start)[1]
            if data.get("period") == Report.Period.MONTHLY
            else period_start
        )
        report, _ = Report.objects.get_or_create(
            website=website,
            period=data.get("period", Report.Period.MONTHLY),
            period_start=period_start,
            defaults={"user": request.user, "period_end": period_end},
        )
        report.period_end = period_end
        report_data = generate_report_data(website, period_start, period_end)
        for field, value in report_data.items():
            setattr(report, field, value)
        report.status = Report.Status.GENERATED
        report.generated_at = timezone.now()
        report.save()

        last_scan = (
            Scan.objects.filter(
                website=website,
                status=Scan.Status.COMPLETED,
                created_at__date__gte=period_start,
                created_at__date__lte=period_end,
            )
            .order_by("-created_at")
            .first()
        )
        payload = ReportSerializer(report).data
        payload["scan_id"] = last_scan.id if last_scan else None
        return Response(payload, status=status.HTTP_201_CREATED)


class ReportListView(APIView):
    """GET /api/v1/reports/ — real monthly Report rows for the user."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Generating a report walks every month and every website. It is done
        # once on first read (or on an explicit refresh), never on each page
        # load: the monthly beat task keeps later months up to date.
        if request.query_params.get("refresh") == "1":
            ensure_monthly_reports(request.user, refresh_current=True)
        elif not Report.objects.filter(user=request.user).exists():
            ensure_monthly_reports(request.user)

        reports = (
            Report.objects.filter(user=request.user)
            .select_related("website")
            .order_by("-period_start", "website__domain")
        )
        return Response(
            {
                "results": ReportSerializer(reports, many=True).data,
                "count": reports.count(),
            }
        )


class ReportDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk: int):
        scan = Scan.objects.filter(id=pk, website__owner=request.user).first()
        if not scan:
            return Response({"detail": "Rapport introuvable."}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "id": scan.id,
            "scan_id": scan.id,
            "domain": scan.website.domain,
            "score": scan.health_score,
            "created_at": scan.created_at.isoformat() if scan.created_at else None,
        })
