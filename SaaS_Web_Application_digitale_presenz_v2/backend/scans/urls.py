from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CheckResultViewSet, JourneyViewSet, ScanViewSet

router = DefaultRouter()
router.register("scans", ScanViewSet, basename="scan")
router.register("scan-journeys", JourneyViewSet, basename="scan-journey")

check_result_list = CheckResultViewSet.as_view({"get": "list"})
check_result_detail = CheckResultViewSet.as_view({"get": "retrieve"})

urlpatterns = [
    path("scans/<int:scan_pk>/results/", check_result_list, name="scan-results-list"),
    path(
        "scans/<int:scan_pk>/results/<int:pk>/",
        check_result_detail,
        name="scan-results-detail",
    ),
    *router.urls,
]
