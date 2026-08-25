from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from scans.models import Scan
from scans.serializers import ScanSerializer

from .models import Website
from .serializers import WebsiteSerializer


@extend_schema(tags=["websites"])
class WebsiteViewSet(ModelViewSet[Website]):
    serializer_class = WebsiteSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return Website.objects.filter(owner=self.request.user).order_by("domain")

    def perform_create(self, serializer: WebsiteSerializer) -> None:
        serializer.save(owner=self.request.user)

    @extend_schema(request=None, responses={202: ScanSerializer, 409: None}, tags=["scans"])
    @action(detail=True, methods=["post"], url_path="scan")
    def scan(self, request: object, pk: str | None = None) -> Response:
        website = self.get_object()
        
        # Prevent concurrent scans for the same website
        active_scans = Scan.objects.filter(
            website=website,
            status__in=[
                Scan.Status.PENDING,
                Scan.Status.QUEUED,
                Scan.Status.RUNNING,
            ],
        ).exists()
        
        if active_scans:
            return Response(
                {"detail": "A scan is already in progress for this website."},
                status=status.HTTP_409_CONFLICT
            )
            
        scan = Scan.objects.create(website=website, trigger=Scan.Trigger.MANUAL, status=Scan.Status.QUEUED)
        
        from scans.tasks import run_authenticated_scan
        run_authenticated_scan.delay(scan.id)
        
        return Response(ScanSerializer(scan).data, status=status.HTTP_202_ACCEPTED)
