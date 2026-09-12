import logging
from datetime import datetime
from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

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
    """
    POST /api/v1/reports/generate/ ou /api/v1/reports/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        website_id = request.data.get("website_id")
        website = Website.objects.filter(id=website_id, owner=request.user).first()
        if not website:
            return Response({"detail": "Site introuvable ou non autorisé."}, status=status.HTTP_404_NOT_FOUND)
        
        last_scan = Scan.objects.filter(website=website, status=Scan.Status.COMPLETED).order_by("-created_at").first()
        return Response({
            "status": "report_generated",
            "website": website.domain,
            "scan_id": last_scan.id if last_scan else None,
            "score": last_scan.health_score if last_scan else None,
            "generated_at": datetime.now().isoformat(),
        }, status=status.HTTP_201_CREATED)


class ReportListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        websites = Website.objects.filter(owner=request.user)
        scans = Scan.objects.filter(website__in=websites, status=Scan.Status.COMPLETED).order_by("-created_at")[:20]
        reports_data = [
            {
                "id": s.id,
                "scan_id": s.id,
                "domain": s.website.domain,
                "score": s.health_score,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in scans
        ]
        return Response({"results": reports_data, "count": len(reports_data)})


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
