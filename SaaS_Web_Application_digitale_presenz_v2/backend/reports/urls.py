from django.urls import path

from .views import (
    GenerateReportView,
    ReportDetailView,
    ReportListView,
    WhiteLabelPDFReportView,
)

# The frontend calls /api/v1/reports/... (see src/api/endpoints.ts).  These
# routes used to be mounted at the API root, so every report request 404'd.
urlpatterns = [
    path("reports/", ReportListView.as_view(), name="report-list"),
    path("reports/generate/", GenerateReportView.as_view(), name="report-generate"),
    path("reports/<int:pk>/", ReportDetailView.as_view(), name="report-detail"),
    path(
        "reports/pdf/<int:scan_id>/",
        WhiteLabelPDFReportView.as_view(),
        name="whitelabel-pdf-report",
    ),
]
