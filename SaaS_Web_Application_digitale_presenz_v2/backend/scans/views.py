"""Scans application views.

All existing endpoints are preserved.  New endpoints are additive.
"""

from __future__ import annotations

from django.db.models import Case, IntegerField, QuerySet, Value, When
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ReadOnlyModelViewSet

from organizations.access import check_result_access_q, scan_access_q, website_access_q
from subscriptions.services.quotas import (
    get_effective_plan_for_organization,
    scans_used_this_month,
)
from websites.models import Website

from .models import CheckResult, Finding, JourneyState, Scan, ScanJourney, ScannerRun
from .serializers import (
    CheckResultSerializer,
    FindingSerializer,
    JourneyCreateSerializer,
    JourneyDetailSerializer,
    JourneyListSerializer,
    ScanListSerializer,
    ScannerRunSerializer,
    ScanSerializer,
)
from .services.exceptions import (
    JourneyConflictError,
    JourneyExpiredError,
    JourneyStateError,
    QuotaExceededError,
)
from .services.journey_service import JourneyService, check_write_permission


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


# ---------------------------------------------------------------------------
# Progressive scan journeys (Lot D)
# ---------------------------------------------------------------------------


def _journey_websites_for(user):
    """Websites whose journeys *user* may read.

    Superusers are not covered by the organization access Q object, so they
    are handled explicitly.
    """
    if user.is_superuser:
        return Website.objects.all()
    return Website.objects.filter(website_access_q(user))


class JourneyWritePermission(permissions.BasePermission):
    """Allow mutations only to Owner/Admin/Analyst on the journey's website."""

    message = "Votre rôle ne permet pas de modifier ce parcours."

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        try:
            check_write_permission(request.user, obj.website)
        except PermissionError:
            return False
        return True


@extend_schema(tags=["scan-journeys"])
class JourneyViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    """Progressive scan journeys.

    create:   POST /api/v1/scan-journeys/
    list:     GET  /api/v1/scan-journeys/
    retrieve: GET  /api/v1/scan-journeys/{id}/
    advance:  POST /api/v1/scan-journeys/{id}/advance/
    cancel:   POST /api/v1/scan-journeys/{id}/cancel/
    """

    permission_classes = [permissions.IsAuthenticated, JourneyWritePermission]

    def get_queryset(self) -> QuerySet[ScanJourney]:
        user = self.request.user
        if not user.is_authenticated:
            return ScanJourney.objects.none()

        qs = (
            ScanJourney.objects.select_related("website", "requested_by")
            .prefetch_related("stages")
            .filter(website__in=_journey_websites_for(user))
            .order_by("-created_at")
        )

        if self.action == "list":
            website_id = self.request.query_params.get("website")
            if website_id:
                qs = qs.filter(website_id=website_id)

            state = self.request.query_params.get("state")
            if state:
                qs = qs.filter(state=state)

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return JourneyCreateSerializer
        if self.action == "list":
            return JourneyListSerializer
        return JourneyDetailSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        """Admit a journey through :class:`JourneyService`.

        The website is resolved through the read scope first: an unknown or
        foreign site is a 404, never a 403, so the endpoint cannot be used to
        probe tenant ids.  The service then enforces the write role.
        """
        serializer = JourneyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        website = (
            _journey_websites_for(request.user)
            .filter(pk=serializer.validated_data["website"])
            .first()
        )
        if website is None:
            raise NotFound("Site introuvable.")

        try:
            journey = JourneyService.create_journey(
                website=website,
                requested_by=request.user,
                trigger_source="api",
            )
        except JourneyConflictError as exc:
            active = (
                ScanJourney.objects.filter(
                    website=website,
                    state__in=[
                        JourneyState.RUNNING,
                        JourneyState.AWAITING_CONFIRMATION,
                    ],
                )
                .only("id", "state")
                .first()
            )
            payload = {"detail": str(exc)}
            if active is not None:
                payload["journey_id"] = active.id
                payload["state"] = active.state
            return Response(payload, status=status.HTTP_409_CONFLICT)
        except QuotaExceededError as exc:
            plan = get_effective_plan_for_organization(website.organization)
            payload = {
                "detail": str(exc),
                "used": scans_used_this_month(organization=website.organization),
                "limit": plan.max_scans_per_month if plan is not None else None,
            }
            return Response(payload, status=status.HTTP_429_TOO_MANY_REQUESTS)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        return Response(
            JourneyDetailSerializer(journey).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses=JourneyDetailSerializer)
    @action(detail=True, methods=["post"])
    def advance(self, request: Request, pk=None) -> Response:
        """Confirm stage 1 and queue stage 2."""
        journey = self.get_object()

        try:
            journey = JourneyService.advance_journey(
                journey_id=journey.id,
                requested_by=request.user,
            )
        except JourneyExpiredError as exc:
            expired_at = (
                ScanJourney.objects.filter(pk=journey.pk)
                .values_list("expires_at", flat=True)
                .first()
            )
            return Response(
                {"detail": str(exc), "expired_at": expired_at},
                status=status.HTTP_410_GONE,
            )
        except JourneyStateError as exc:
            current_state = (
                ScanJourney.objects.filter(pk=journey.pk)
                .values_list("state", flat=True)
                .first()
            )
            return Response(
                {"detail": str(exc), "current_state": current_state},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except JourneyConflictError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        return Response(JourneyDetailSerializer(journey).data)

    @extend_schema(request=None, responses=JourneyDetailSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk=None) -> Response:
        """Cancel a running or awaiting journey."""
        journey = self.get_object()

        try:
            journey = JourneyService.cancel_journey(
                journey_id=journey.id,
                requested_by=request.user,
            )
        except JourneyStateError as exc:
            current_state = (
                ScanJourney.objects.filter(pk=journey.pk)
                .values_list("state", flat=True)
                .first()
            )
            return Response(
                {"detail": str(exc), "current_state": current_state},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        return Response(JourneyDetailSerializer(journey).data)
