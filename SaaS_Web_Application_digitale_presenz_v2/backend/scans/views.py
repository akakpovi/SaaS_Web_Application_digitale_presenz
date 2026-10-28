"""Scans application views.

All existing endpoints are preserved.  New endpoints are additive.
"""

from __future__ import annotations

from django.db.models import Case, IntegerField, QuerySet, Value, When
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from organizations.access import check_result_access_q, scan_access_q

from .models import CheckResult, Finding, Scan, ScannerRun
from .serializers import (
    CheckResultSerializer,
    FindingSerializer,
    ScanListSerializer,
    ScannerRunSerializer,
    ScanSerializer,
)


@extend_schema(tags=["scans"])
class ScanViewSet(ReadOnlyModelViewSet[Scan]):
    """List and retrieve authenticated scans.

    Supports filtering via query params:
    - ``?website=<id>`` — filter by website
    - ``?status=running,completed`` — comma-separated status values
    - ``?scan_type=health`` — filter by scan type
    """

    def get_serializer_class(self):
        if self.action == "list":
            return ScanListSerializer
        return ScanSerializer

    def get_queryset(self) -> QuerySet[Scan]:
        qs = (
            Scan.objects.filter(scan_access_q(self.request.user))
            .select_related("website", "website__organization")
            .prefetch_related("check_results")
            .distinct()
            .order_by("-created_at")
        )

        if self.action == "list":
            # Filter by website.
            website_id = self.request.query_params.get("website")
            if website_id:
                qs = qs.filter(website_id=website_id)

            # Filter by status (comma-separated).
            status_param = self.request.query_params.get("status")
            if status_param:
                statuses = [s.strip() for s in status_param.split(",") if s.strip()]
                qs = qs.filter(status__in=statuses)

            # Filter by scan_type.
            scan_type = self.request.query_params.get("scan_type")
            if scan_type:
                qs = qs.filter(scan_type=scan_type)

        return qs

    @extend_schema(
        summary="List scanner runs for a scan",
        responses={200: ScannerRunSerializer(many=True)},
        tags=["scans"],
    )
    @action(detail=True, methods=["get"], url_path="scanner-runs")
    def scanner_runs(self, request: Request, pk: int = None) -> Response:
        """GET /api/v1/scans/{id}/scanner-runs/"""
        scan = self.get_object()
        runs = ScannerRun.objects.filter(scan=scan).order_by("created_at")
        serializer = ScannerRunSerializer(runs, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="List findings for a scan",
        parameters=[
            OpenApiParameter("severity", description="Filter by severity (info/low/medium/high/critical)", required=False),
            OpenApiParameter("category", description="Filter by category (ssl/dns/security/etc.)", required=False),
            OpenApiParameter("status", description="Filter by finding status (pass/fail/warning/etc.)", required=False),
        ],
        responses={200: FindingSerializer(many=True)},
        tags=["scans"],
    )
    @action(detail=True, methods=["get"], url_path="findings")
    def findings(self, request: Request, pk: int = None) -> Response:
        """GET /api/v1/scans/{id}/findings/

        Supports ``?severity=``, ``?category=``, ``?status=`` query params.
        """
        scan = self.get_object()
        # Severity is a label, not an ordinal: ordering by the raw column put
        # "medium" first and "high"/"critical" after "info".  Rank it
        # explicitly so the most serious finding is always listed first.
        severity_rank = Case(
            *[
                When(severity=label, then=Value(rank))
                for label, rank in (
                    ("critical", 5),
                    ("high", 4),
                    ("medium", 3),
                    ("low", 2),
                    ("info", 1),
                )
            ],
            default=Value(0),
            output_field=IntegerField(),
        )
        qs = (
            Finding.objects.filter(scanner_run__scan=scan)
            .select_related("scanner_run")
            .annotate(severity_rank=severity_rank)
            .order_by("-severity_rank", "category", "check_code", "id")
        )

        severity = request.query_params.get("severity")
        if severity:
            qs = qs.filter(severity=severity)

        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        finding_status = request.query_params.get("status")
        if finding_status:
            qs = qs.filter(status=finding_status)

        serializer = FindingSerializer(qs, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Get scan recommendations",
        tags=["scans"],
    )
    @action(detail=True, methods=["get"], url_path="recommendations")
    def recommendations(self, request: Request, pk: int = None) -> Response:
        """GET /api/v1/scans/{id}/recommendations/"""
        scan = self.get_object()
        from scans.services.recommendation_engine import RecommendationEngine
        engine = RecommendationEngine(scan)
        return Response({"recommendations": engine.to_dict_list()})


@extend_schema(tags=["scans"])
class CheckResultViewSet(ReadOnlyModelViewSet[CheckResult]):
    serializer_class = CheckResultSerializer

    def get_queryset(self) -> QuerySet[CheckResult]:
        scan_id = self.kwargs["scan_pk"]
        return (
            CheckResult.objects
            .filter(
                check_result_access_q(self.request.user),
                scan_id=scan_id,
            )
            .select_related("scan")
            .distinct()
        )

    def get_object(self) -> CheckResult:
        try:
            return super().get_object()
        except NotFound:
            raise
