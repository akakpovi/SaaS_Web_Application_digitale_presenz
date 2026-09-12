from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from monitoring.models import MonitoringConfig
from monitoring.serializers import MonitoringConfigSerializer
from websites.models import Website


class MonitoringConfigListView(generics.ListAPIView):
    """GET /api/v1/monitoring/ — list all monitoring configs for the authenticated user."""
    serializer_class = MonitoringConfigSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MonitoringConfig.objects.filter(
            website__owner=self.request.user
        ).select_related("website")


class MonitoringConfigDetailView(APIView):
    """GET / PUT / PATCH / DELETE /api/v1/monitoring/websites/<website_id>/"""
    permission_classes = [permissions.IsAuthenticated]

    def _get_config(self, website_id: int) -> MonitoringConfig:
        website = get_object_or_404(Website, pk=website_id, owner=self.request.user)
        config, _ = MonitoringConfig.objects.get_or_create(
            website=website,
            defaults={"enabled": True},
        )
        return config

    def get(self, request, website_id: int) -> Response:
        config = self._get_config(website_id)
        return Response(MonitoringConfigSerializer(config).data)

    def put(self, request, website_id: int) -> Response:
        config = self._get_config(website_id)
        serializer = MonitoringConfigSerializer(config, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request, website_id: int) -> Response:
        config = self._get_config(website_id)
        serializer = MonitoringConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, website_id: int) -> Response:
        config = self._get_config(website_id)
        config.enabled = False
        config.save(update_fields=["enabled", "updated_at"])
        return Response({"detail": "Monitoring disabled."}, status=status.HTTP_200_OK)


class TriggerImmediateScanView(APIView):
    """POST /api/v1/monitoring/websites/<website_id>/scan/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, website_id: int) -> Response:
        website = get_object_or_404(Website, pk=website_id, owner=request.user)
        from scans.models import Scan
        from scans.tasks import run_authenticated_scan

        scan = Scan.objects.create(
            website=website,
            trigger=Scan.Trigger.MANUAL,
            status=Scan.Status.QUEUED,
        )
        run_authenticated_scan.delay(scan.id)
        return Response(
            {"detail": "Scan queued.", "scan_id": scan.id},
            status=status.HTTP_202_ACCEPTED,
        )
