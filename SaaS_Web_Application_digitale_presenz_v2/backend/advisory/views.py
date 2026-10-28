"""REST endpoints for AI-generated scan recommendations.

Routes are organization-scoped through ``scan.website`` and enforce the
Owner/Admin/Analyst/Viewer matrix.  A failed run is served from the
deterministic engine only; nothing is written back under the guise of an AI
recommendation.
"""

from __future__ import annotations

from django.db.models import Case, IntegerField, Value, When
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from advisory.models import AIRecommendation, AIRecommendationRun, SecurityFinding
from advisory.parsers import MAX_REPORT_BYTES, ReportParseError, parse_report
from advisory.permissions import (
    can_manage_recommendations,
    get_scan_for_user,
    role_for_website,
)
from advisory.serializers import (
    AIRecommendationSerializer,
    AdvisorChatRequestSerializer,
    AdvisorChatResponseSerializer,
    AssetSecurityFindingSerializer,
)
from advisory.services.advisor import get_recommendations_for_run
from advisory.services.ingestion import ingest_report
from advisory.services.security_advisor import (
    AdvisorUnavailable,
    answer_security_question,
)
from organizations.access import (
    DELETE_ROLES,
    READ_ROLES,
    WRITE_ROLES,
    role_for_organization,
)
from organizations.models import Organization
from websites.models import Website

_NOT_FOUND = {"detail": "Scan not found."}
_RECOMMENDATION_NOT_FOUND = {"detail": "Recommendation not found."}
_ORGANIZATION_NOT_FOUND = {"detail": "Organization not found."}


def _run_payload(run: AIRecommendationRun | None) -> dict | None:
    if run is None:
        return None
    return {
        "id": str(run.id),
        "status": run.status,
        "model_used": run.model_used,
        "attempts": run.attempts,
        "error_code": run.error_code,
        "completed_at": run.completed_at,
    }


class RecommendationListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List recommendations for one scan",
        parameters=[
            OpenApiParameter(
                "scan_id",
                int,
                required=True,
                description="Scan whose recommendations should be returned.",
            )
        ],
        tags=["advisory"],
    )
    def get(self, request: Request) -> Response:
        raw_scan_id = request.query_params.get("scan_id")
        if not raw_scan_id:
            return Response(
                {"detail": "scan_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            scan_id = int(raw_scan_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "scan_id must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scan = get_scan_for_user(scan_id, request.user)
        if scan is None:
            return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        run = (
            AIRecommendationRun.objects.filter(scan=scan)
            .order_by("-created_at")
            .first()
        )
        if run is None:
            return Response(
                {
                    "scan_id": scan.pk,
                    "run": None,
                    "source": "none",
                    "persisted": False,
                    "recommendations": [],
                }
            )

        result = get_recommendations_for_run(run, scan)
        if result.used_fallback:
            source = "deterministic"
        elif result.in_progress:
            source = "none"
        else:
            source = "ai"

        return Response(
            {
                "scan_id": scan.pk,
                "run": _run_payload(run),
                "source": source,
                "persisted": source == "ai",
                "recommendations": result.recommendations,
            }
        )


class RecommendationDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Accept or dismiss an AI recommendation",
        tags=["advisory"],
    )
    def post(self, request: Request, pk, decision: str) -> Response:
        recommendation = (
            AIRecommendation.objects.select_related(
                "run",
                "run__scan",
                "run__scan__website",
                "finding",
                "check_result",
            )
            .filter(pk=pk)
            .first()
        )
        if recommendation is None:
            return Response(
                _RECOMMENDATION_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND,
            )

        scan = get_scan_for_user(recommendation.run.scan_id, request.user)
        if scan is None:
            # Do not reveal that the recommendation exists in another tenant.
            return Response(
                _RECOMMENDATION_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND,
            )

        role = role_for_website(request.user, scan.website)
        if not can_manage_recommendations(request.user, scan.website):
            return Response(
                {
                    "detail": (
                        "Your organization role does not allow changing "
                        "recommendation decisions."
                    ),
                    "role": role,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if decision == "accept":
            recommendation.accept(request.user)
        else:
            recommendation.dismiss(request.user)

        return Response(AIRecommendationSerializer(recommendation).data)


class OrganizationAdvisorChatView(APIView):
    """POST /api/v1/organizations/<org>/ai-advisor/chat/.

    The organization comes from the URL and the role from the database: the
    client never supplies a tenant, a findings list or a prompt.  The advisor
    only reads this organization's *open* findings and only explains them.

    Access is limited to roles that can act on findings (owner/admin/analyst).
    A viewer gets 403 instead of silently spending the organization's AI
    budget, and an outsider gets 404 so the API does not confirm that the
    organization exists.
    """

    permission_classes = [IsAuthenticated]
    # Every message costs real model credits; the scoped rate comes from
    # REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["advisor_chat"].
    throttle_scope = "advisor_chat"

    @extend_schema(
        summary="Ask the AI security advisor about open findings",
        request=AdvisorChatRequestSerializer,
        responses={
            200: AdvisorChatResponseSerializer,
            503: OpenApiResponse(
                description=(
                    "The AI provider is unavailable, rate limited or not "
                    "configured; the platform keeps serving the rest of the API."
                )
            ),
        },
        tags=["advisory"],
    )
    def post(self, request: Request, organization_id) -> Response:
        organization = Organization.objects.filter(pk=organization_id).first()
        if organization is None:
            return Response(
                _ORGANIZATION_NOT_FOUND, status=status.HTTP_404_NOT_FOUND
            )
        role = role_for_organization(request.user, organization)
        if role is None:
            # Same 404 as a missing organization: no tenant enumeration.
            return Response(
                _ORGANIZATION_NOT_FOUND, status=status.HTTP_404_NOT_FOUND
            )
        if role not in WRITE_ROLES:
            return Response(
                {
                    "detail": (
                        "Your organization role does not allow using the AI "
                        "security advisor."
                    ),
                    "role": role,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AdvisorChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Optional per-asset focus, chosen from the asset page.  The asset is
        # resolved inside this organization only: another tenant's asset id
        # answers exactly like a missing one.
        asset = None
        asset_id = serializer.validated_data.get("asset_id")
        if asset_id is not None:
            asset = Website.objects.filter(
                pk=asset_id, organization=organization
            ).first()
            if asset is None:
                return Response(
                    {"detail": "Asset not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        try:
            answer = answer_security_question(
                organization,
                serializer.validated_data["message"],
                asset=asset,
            )
        except AdvisorUnavailable as exc:
            # A provider outage is a 503, never a 500: the platform stays up.
            response = Response(
                {"error": exc.code, "detail": exc.detail},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
            if exc.retry_after:
                response["Retry-After"] = str(max(1, int(round(exc.retry_after))))
            response["Cache-Control"] = "no-store"
            return response

        response = Response(
            {
                "reply": answer.reply,
                "model": answer.model,
                "findings_included": answer.findings_included,
                "context_truncated": answer.context_truncated,
                "request_id": answer.request_id,
            },
            status=status.HTTP_200_OK,
        )
        response["Cache-Control"] = "no-store"
        return response


class AssetScanReportImportView(APIView):
    """POST /api/v1/organizations/<org>/assets/<asset>/scans/import/.

    Accepts one ZAP or Nuclei report as a multipart ``file`` upload, detects
    its format, ingests it into ``SecurityFinding`` and reports the counts.

    Authorization is checked before the file is read: the organization comes
    from the URL, the role from the database, and the asset must belong to
    that same organization (an asset of another tenant answers exactly like a
    missing one, so the API cannot be used to enumerate assets).

    Uploading a report is a bulk write over the tenant's findings, so it is
    reserved to owners and administrators; analysts and viewers can read the
    resulting findings but not replace the set of open ones.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Import an OWASP ZAP or Nuclei report for one asset",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "format": "binary"},
                    "source": {
                        "type": "string",
                        "enum": ["zap", "nuclei"],
                        "description": "Optional; detected from the file when omitted.",
                    },
                },
                "required": ["file"],
            }
        },
        responses={
            200: OpenApiResponse(description="Ingestion counters for the asset."),
            400: OpenApiResponse(description="Missing, oversized or unrecognised report."),
            403: OpenApiResponse(description="Role does not allow importing reports."),
            404: OpenApiResponse(description="Unknown organization or asset."),
        },
        tags=["advisory"],
    )
    def post(self, request: Request, organization_id, asset_id) -> Response:
        organization = Organization.objects.filter(pk=organization_id).first()
        if organization is None:
            return Response(
                _ORGANIZATION_NOT_FOUND, status=status.HTTP_404_NOT_FOUND
            )
        role = role_for_organization(request.user, organization)
        if role is None:
            # Same answer as a missing organization: no tenant enumeration.
            return Response(
                _ORGANIZATION_NOT_FOUND, status=status.HTTP_404_NOT_FOUND
            )
        if role not in DELETE_ROLES:
            return Response(
                {
                    "detail": (
                        "Your organization role does not allow importing "
                        "scanner reports."
                    ),
                    "role": role,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        asset = Website.objects.filter(
            pk=asset_id, organization=organization
        ).first()
        if asset is None:
            return Response(
                {"detail": "Asset not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {
                    "error": "file_required",
                    "detail": "Attach the report as a multipart 'file' field.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if upload.size is not None and upload.size > MAX_REPORT_BYTES:
            return Response(
                {
                    "error": "report_too_large",
                    "detail": "The uploaded report is too large.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Read at most one byte past the limit: an oversized stream must never
        # be buffered whole just to be rejected.
        raw = upload.read(MAX_REPORT_BYTES + 1)
        if len(raw) > MAX_REPORT_BYTES:
            return Response(
                {
                    "error": "report_too_large",
                    "detail": "The uploaded report is too large.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return Response(
                {
                    "error": "invalid_encoding",
                    "detail": "The report must be UTF-8 encoded JSON.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        requested_source = request.data.get("source")
        if not isinstance(requested_source, str) or not requested_source.strip():
            requested_source = None

        try:
            report = parse_report(text, source=requested_source)
        except ReportParseError as exc:
            return Response(
                {"error": exc.code, "detail": exc.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        outcome = ingest_report(organization, asset, report)
        response = Response(
            {
                "asset_id": asset.pk,
                "source": outcome.source,
                "received": outcome.received,
                "created": outcome.created,
                "updated": outcome.updated,
                "resolved": outcome.resolved,
            },
            status=status.HTTP_200_OK,
        )
        # The counters describe one tenant's asset: never cacheable.
        response["Cache-Control"] = "no-store"
        return response


recommendation_list = RecommendationListView.as_view()
recommendation_accept = RecommendationDecisionView.as_view()
recommendation_dismiss = RecommendationDecisionView.as_view()
organization_advisor_chat = OrganizationAdvisorChatView.as_view()
class AssetSecurityFindingListView(generics.ListAPIView):
    """GET /api/v1/organizations/<org>/assets/<asset>/security/findings/.

    The current vulnerability set of one asset, newest/most severe first.
    Every member role may read it (viewers included); the asset is resolved
    inside the organization, so another tenant's asset id is a 404.

    ``?status=open|resolved|all`` (default ``open``), ``?severity=`` and
    ``?source=zap|nuclei`` narrow the list.  Raw evidence is never returned.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = AssetSecurityFindingSerializer

    _SEVERITY_ORDER = {
        SecurityFinding.Severity.CRITICAL: 0,
        SecurityFinding.Severity.HIGH: 1,
        SecurityFinding.Severity.MEDIUM: 2,
        SecurityFinding.Severity.LOW: 3,
        SecurityFinding.Severity.INFO: 4,
    }

    def get_queryset(self):
        organization = Organization.objects.filter(
            pk=self.kwargs["organization_id"]
        ).first()
        if organization is None or role_for_organization(
            self.request.user, organization
        ) not in READ_ROLES:
            raise Http404("Organization not found.")

        asset = Website.objects.filter(
            pk=self.kwargs["asset_id"], organization=organization
        ).first()
        if asset is None:
            raise Http404("Asset not found.")

        queryset = SecurityFinding.objects.filter(
            organization=organization, asset=asset
        )

        raw_status = str(
            self.request.query_params.get("status") or "open"
        ).strip().lower()
        if raw_status != "all":
            if raw_status not in SecurityFinding.Status.values:
                raise ValidationError({"status": "Invalid finding status."})
            queryset = queryset.filter(status=raw_status)

        severity = str(
            self.request.query_params.get("severity") or ""
        ).strip().lower()
        if severity:
            if severity not in SecurityFinding.Severity.values:
                raise ValidationError({"severity": "Invalid severity."})
            queryset = queryset.filter(severity=severity)

        source = str(
            self.request.query_params.get("source") or ""
        ).strip().lower()
        if source:
            queryset = queryset.filter(scanner_source=source)

        severity_rank = Case(
            *[
                When(severity=label, then=Value(rank))
                for label, rank in self._SEVERITY_ORDER.items()
            ],
            default=Value(99),
            output_field=IntegerField(),
        )
        return queryset.annotate(severity_rank=severity_rank).order_by(
            "severity_rank", "-detected_at"
        )

    def list(self, request: Request, *args, **kwargs) -> Response:
        response = super().list(request, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


asset_scan_report_import = AssetScanReportImportView.as_view()
asset_security_findings = AssetSecurityFindingListView.as_view()
