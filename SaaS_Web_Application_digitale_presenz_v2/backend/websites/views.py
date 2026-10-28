"""Websites application views.

Backward compatible: all existing endpoints preserved.
New additions:
- ``trigger_scan`` now accepts ``scan_type`` in the request body.
- ``active_scan`` endpoint returns the current active scan for a website.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from organizations.access import WRITE_ROLES, role_for_organization, website_access_q
from organizations.models import Membership, Organization
from organizations.services import ensure_personal_organization
from scans.models import HealthStatus, Scan
from scans.serializers import ScanSerializer
from scans.tasks import run_authenticated_scan

from .models import Website
from .permissions import WebsiteRolePermission
from .serializers import WebsiteDetailSerializer, WebsiteListSerializer, WebsiteSerializer


class WebsiteViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, WebsiteRolePermission]

    def get_queryset(self):
        return (
            Website.objects.filter(website_access_q(self.request.user))
            .select_related("organization")
            .distinct()
            .order_by("-created_at")
        )

    def _resolve_target_organization(self, request: Request) -> Organization:
        """Resolve the tenant a new website belongs to.

        An explicit ``organization_id`` must reference an organization the
        caller can read; a non-member gets 404 to avoid leaking tenant ids,
        while a viewer gets 403 because its role cannot create resources.
        Without an explicit id the personal organization is preferred.  If the
        user belongs to exactly one writable team organization it is used
        automatically; ambiguity is a 400 asking for ``organization_id``.
        """
        raw_organization_id = (
            (request.data or {}).get("organization_id")
            or (request.data or {}).get("organization")
        )
        if raw_organization_id:
            try:
                organization = Organization.objects.filter(
                    pk=raw_organization_id
                ).first()
            except (DjangoValidationError, ValueError, TypeError):
                raise ValidationError({"organization_id": "Invalid organization id."})
            if organization is None:
                raise NotFound("Organization not found.")
            role = role_for_organization(request.user, organization)
            if role is None:
                raise NotFound("Organization not found.")
            if role not in WRITE_ROLES:
                raise PermissionDenied(
                    "Your organization role does not allow adding a website."
                )
            return organization

        personal = Organization.objects.filter(
            billing_owner=request.user,
            is_personal=True,
        ).first()
        if personal is not None:
            return personal

        writable_memberships = list(
            Membership.objects.filter(
                user=request.user,
                role__in=WRITE_ROLES,
            ).select_related("organization")[:2]
        )
        if len(writable_memberships) == 1:
            return writable_memberships[0].organization
        if len(writable_memberships) > 1:
            raise ValidationError(
                {
                    "organization_id": (
                        "You belong to several organizations; specify "
                        "organization_id to create a website."
                    )
                }
            )
        return ensure_personal_organization(request.user)

    def create(self, request: Request, *args, **kwargs) -> Response:
        organization = self._resolve_target_organization(request)
        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), "organization": organization},
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return WebsiteDetailSerializer
        elif self.action == "list":
            return WebsiteListSerializer
        return WebsiteSerializer

    def perform_create(self, serializer):
        from subscriptions.services.quotas import assert_can_add_website

        organization = serializer.context.get("organization")
        assert_can_add_website(self.request.user, organization=organization)
        serializer.save(owner=self.request.user, organization=organization)

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

        from subscriptions.services.quotas import assert_can_scan

        assert_can_scan(request.user, organization=website.organization)

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
