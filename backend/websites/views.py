from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Website
from .serializers import WebsiteSerializer, WebsiteDetailSerializer
from scans.models import Scan, HealthStatus
from scans.serializers import ScanSerializer
from scans.tasks import run_authenticated_scan


class WebsiteViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Website.objects.filter(owner=self.request.user).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return WebsiteDetailSerializer
        return WebsiteSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"], url_path="scan")
    def trigger_scan(self, request, pk=None):
        website = self.get_object()
        active_scan = Scan.objects.filter(
            website=website,
            status__in=[Scan.Status.QUEUED, Scan.Status.RUNNING, Scan.Status.PENDING]
        ).first()
        if active_scan:
            return Response(
                {"detail": "A scan is already in progress for this website."},
                status=status.HTTP_409_CONFLICT
            )

        scan = Scan.objects.create(
            website=website,
            trigger=Scan.Trigger.MANUAL,
            status=Scan.Status.QUEUED,
            health_status=HealthStatus.NEUTRAL.value if hasattr(HealthStatus.NEUTRAL, "value") else str(HealthStatus.NEUTRAL),
        )
        run_authenticated_scan.delay(scan.id)
        return Response(ScanSerializer(scan).data, status=status.HTTP_202_ACCEPTED)
