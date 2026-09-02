from django.urls import path
from .views import (
    GenerateReportView,
    ReportListView,
    ReportDetailView,
    WhiteLabelPDFReportView,
)

urlpatterns = [
    path("", ReportListView.as_view(), name="report-list"),
    path("generate/", GenerateReportView.as_view(), name="report-generate"),
    path("<int:pk>/", ReportDetailView.as_view(), name="report-detail"),
    path("pdf/<int:scan_id>/", WhiteLabelPDFReportView.as_view(), name="whitelabel-pdf-report"),
]
