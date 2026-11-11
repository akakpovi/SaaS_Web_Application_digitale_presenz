from django.urls import path
from .views import (
    PublicScanEndpointView,
    PublicScanStatusView,
    PublicScanEmailView,
    PublicScanConvertView,
)

urlpatterns = [
    # Routes Phase 1 & 2
    path("scan/", PublicScanEndpointView.as_view(), name="public-scan"),
    path(
        "scan/<str:scan_id>/status/",
        PublicScanStatusView.as_view(),
        name="public-scan-status",
    ),
    path(
        "scan/<str:scan_id>/email/",
        PublicScanEmailView.as_view(),
        name="public-scan-email",
    ),
    path(
        "scan/<str:scan_id>/convert/",
        PublicScanConvertView.as_view(),
        name="public-scan-convert",
    ),
    # Rétrocompatibilité legacy routes (test_legacy_public_checker)
    path("check/", PublicScanEndpointView.as_view(), name="public-check"),
    path(
        "check/<str:scan_id>/",
        PublicScanStatusView.as_view(),
        name="public-check-detail",
    ),
    path(
        "check/<str:scan_id>/status/",
        PublicScanStatusView.as_view(),
        name="public-check-status",
    ),
    path(
        "<str:scan_id>/status/",
        PublicScanStatusView.as_view(),
        name="public-direct-status",
    ),
    path("<str:scan_id>/", PublicScanStatusView.as_view(), name="public-direct"),
]
