from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import CheckResult, Scan
from .serializers import CheckResultSerializer, ScanSerializer


@extend_schema(tags=["scans"])
class ScanViewSet(ReadOnlyModelViewSet[Scan]):
    serializer_class = ScanSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return Scan.objects.filter(website__owner=self.request.user).select_related("website").prefetch_related("check_results")


@extend_schema(tags=["scans"])
class CheckResultViewSet(ReadOnlyModelViewSet[CheckResult]):
    serializer_class = CheckResultSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        scan_id = self.kwargs["scan_pk"]
        return CheckResult.objects.filter(scan_id=scan_id, scan__website__owner=self.request.user).select_related("scan")

    def get_object(self) -> CheckResult:
        try:
            return super().get_object()
        except NotFound:
            # A scoped 404 intentionally does not reveal another user's scan.
            raise
