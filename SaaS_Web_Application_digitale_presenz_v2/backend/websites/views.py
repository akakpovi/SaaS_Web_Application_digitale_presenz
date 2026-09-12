"""Websites application views.

Backward compatible: all existing endpoints preserved.
New additions:
- ``trigger_scan`` now accepts ``scan_type`` in the request body.
- ``active_scan`` endpoint returns the current active scan for a website.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from scans.models import HealthStatus, Scan
from scans.serializers import ScanSerializer
from scans.tasks import run_authenticated_scan

from .models import Website
from .serializers import WebsiteDetailSerializer, WebsiteListSerializer, WebsiteSerializer


class WebsiteViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Website.objects.filter(owner=self.request.user).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return WebsiteDetailSerializer
        elif self.action == "list":
            return WebsiteListSerializer
        return WebsiteSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @extend_schema(
        summary="Trigger a new scan",
        description=(
            "Queue a new scan for this website.  Returns 202 with the queued scan "
            "or 409 if a scan is already active.\n\n"
            "**scan_type** (optional): `health` (default), `security`, or `full`.\n"
            "Omitting `scan_type` keeps full backward compatibility with the existing frontend."
        ),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "scan_type": {
                        "type": "string",
                        "enum": ["health", "security", "full"],
                        "default": "health",
                        "description": "Type of scan to run. Defaults to 'health'.",
                    }
                },
            }
        },
        responses={
            202: ScanSerializer,
            409: OpenApiResponse(description="A scan is already active for this website."),
        },
        tags=["websites"],
    )
    @action(detail=True, methods=["post"], url_path="scan")
    def trigger_scan(self, request: Request, pk: int = None) -> Response:
        """POST /api/v1/websites/{id}/scan/

        Creates a QUEUED scan and dispatches it to Celery.
        Returns 409 if an active scan already exists.

        ``scan_type`` defaults to ``health`` when not provided, preserving
        backward compatibility with the current frontend.
        """
        website = self.get_object()

        # Check for active scan (409).
        active_scan = Scan.objects.filter(
            website=website,
            status__in=[Scan.Status.QUEUED, Scan.Status.RUNNING, Scan.Status.PENDING],
        ).first()
        if active_scan:
            return Response(
                {
                    "detail": "A scan is already in progress for this website.",
                    "scan_already_running": True,
                    "active_scan_id": active_scan.id,
                    "active_scan_status": active_scan.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Parse scan_type from request body; default to HEALTH.
        raw_scan_type = (request.data or {}).get("scan_type", "").strip().lower()
        allowed = {c.lower() for c, _ in Scan.ScanType.choices}
        if raw_scan_type and raw_scan_type not in allowed:
            return Response(
                {
                    "detail": f"Invalid scan_type '{raw_scan_type}'. "
                              f"Allowed values: {sorted(allowed)}."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        scan_type = raw_scan_type or Scan.ScanType.HEALTH

        scan = Scan.objects.create(
            website=website,
            trigger=Scan.Trigger.MANUAL,
            status=Scan.Status.QUEUED,
            scan_type=scan_type,
            health_status=HealthStatus.NEUTRAL,
        )
        run_authenticated_scan.delay(scan.id)

        return Response(ScanSerializer(scan).data, status=status.HTTP_202_ACCEPTED)

    @extend_schema(
        summary="Get the active (running or queued) scan",
        description=(
            "Returns the current active scan for this website, or 404 if no scan "
            "is currently queued or running."
        ),
        responses={
            200: ScanSerializer,
            404: OpenApiResponse(description="No active scan."),
        },
        tags=["websites"],
    )
    @action(detail=True, methods=["get"], url_path="active_scan")
    def active_scan(self, request: Request, pk: int = None) -> Response:
        """GET /api/v1/websites/{id}/active_scan/"""
        website = self.get_object()
        scan = Scan.objects.filter(
            website=website,
            status__in=[Scan.Status.QUEUED, Scan.Status.RUNNING, Scan.Status.PENDING],
        ).order_by("-created_at").first()

        if scan is None:
            return Response(
                {"detail": "No active scan for this website."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ScanSerializer(scan).data)
