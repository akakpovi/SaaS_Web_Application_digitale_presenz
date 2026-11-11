from django.db.models import Q
from django.http import Http404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from monitoring.models import MonitoringConfig
from monitoring.serializers import MonitoringConfigSerializer
from monitoring.services import build_overview
from organizations.access import (
    READ_ROLES,
    WRITE_ROLES,
    role_for_website,
    website_access_q,
)
from websites.models import Website


def _websites_for(user):
    """Websites the user may read, through their organization membership."""
    return Website.objects.filter(website_access_q(user))


def _accessible_website(user, website_id: int) -> Website:
    """Resolve a website through membership, not through its creator field.

    An outsider gets 404 (not 403) so the endpoint cannot be used to probe
    which ids exist in other tenants.
    """
    website = _websites_for(user).filter(pk=website_id).first()
    if website is None:
        raise Http404("Website not found.")
    return website


def _require_write(user, website: Website) -> str:
    role = role_for_website(user, website)
    if role not in WRITE_ROLES:
        raise PermissionDenied(
            "Your organization role does not allow changing monitoring settings."
        )
    return role


class MonitoringOverviewView(APIView):
    """GET /api/v1/monitoring/overview/?period=24H|7D|30D|90D&website_id=N

    Real aggregates only: uptime is computed from the ``uptime`` CheckResult
    of completed scans, the timeline is built from stored alerts and scans.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        raw_website_id = request.query_params.get("website_id")
        website_id: int | None = None
        if raw_website_id not in (None, "", "all"):
            try:
                website_id = int(raw_website_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "website_id must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not _websites_for(request.user).filter(pk=website_id).exists():
                return Response(
                    {"detail": "Website not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        payload = build_overview(
            request.user,
            request.query_params.get("period"),
            website_id,
        )
        return Response(payload)


class MonitoringConfigListView(generics.ListAPIView):
    """GET /api/v1/monitoring/ — monitoring configs of the user's websites."""

    serializer_class = MonitoringConfigSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            MonitoringConfig.objects.filter(
                Q(website__organization__billing_owner=self.request.user)
                | Q(website__organization__memberships__user=self.request.user)
                | Q(
                    website__organization__isnull=True, website__owner=self.request.user
                )
            )
            .select_related("website")
            .distinct()
        )


class MonitoringConfigDetailView(APIView):
    """GET / PUT / PATCH / DELETE /api/v1/monitoring/websites/<website_id>/"""

    permission_classes = [permissions.IsAuthenticated]

    def _get_config(self, website_id: int) -> tuple[MonitoringConfig, Website]:
        website = _accessible_website(self.request.user, website_id)
        config, _ = MonitoringConfig.objects.get_or_create(website=website)
        return config, website

    def get(self, request, website_id: int) -> Response:
        config, _website = self._get_config(website_id)
        return Response(MonitoringConfigSerializer(config).data)

    def put(self, request, website_id: int) -> Response:
        config, website = self._get_config(website_id)
        _require_write(request.user, website)
        serializer = MonitoringConfigSerializer(config, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request, website_id: int) -> Response:
        config, website = self._get_config(website_id)
        _require_write(request.user, website)
        serializer = MonitoringConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, website_id: int) -> Response:
        config, website = self._get_config(website_id)
        _require_write(request.user, website)
        config.enabled = False
        config.save(update_fields=["enabled", "updated_at"])
        return Response({"detail": "Monitoring disabled."}, status=status.HTTP_200_OK)


class TriggerImmediateScanView(APIView):
    """POST /api/v1/monitoring/websites/<website_id>/scan/

    Body: ``{"scan_type": "health"|"security"|"full"}`` (optional, defaults to
    the website's configured monitoring policy).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, website_id: int) -> Response:
        website = _accessible_website(request.user, website_id)
        _require_write(request.user, website)

        from scans.models import Scan
        from scans.tasks import run_authenticated_scan
        from subscriptions.services.quotas import assert_can_scan

        assert_can_scan(request.user, organization=website.organization)

        active = Scan.objects.filter(
            website=website,
            status__in=[Scan.Status.PENDING, Scan.Status.QUEUED, Scan.Status.RUNNING],
        ).first()
        if active is not None:
            return Response(
                {
                    "detail": "A scan is already in progress for this website.",
                    "scan_already_running": True,
                    "active_scan_id": active.id,
                    "active_scan_status": active.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        raw_scan_type = (
            str((request.data or {}).get("scan_type", "") or "").strip().lower()
        )
        allowed = {choice.lower() for choice, _label in Scan.ScanType.choices}
        if raw_scan_type and raw_scan_type not in allowed:
            return Response(
                {
                    "detail": f"Invalid scan_type '{raw_scan_type}'. "
                    f"Allowed values: {sorted(allowed)}."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        config, _ = MonitoringConfig.objects.get_or_create(website=website)
        scan_type = raw_scan_type or config.scan_type or Scan.ScanType.HEALTH

        scan = Scan.objects.create(
            website=website,
            trigger=Scan.Trigger.MANUAL,
            status=Scan.Status.QUEUED,
            scan_type=scan_type,
        )
        run_authenticated_scan.delay(scan.id)
        return Response(
            {
                "detail": "Scan queued.",
                "scan_id": scan.id,
                "scan_type": scan.scan_type,
            },
            status=status.HTTP_202_ACCEPTED,
        )
