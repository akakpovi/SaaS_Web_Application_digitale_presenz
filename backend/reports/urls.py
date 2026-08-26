from django.urls import path

from reports.views import GenerateReportView, ReportDetailView, ReportListView

urlpatterns = [
    path("reports/",            ReportListView.as_view(),    name="report-list"),
    path("reports/generate/",   GenerateReportView.as_view(), name="report-generate"),
    path("reports/<uuid:pk>/",  ReportDetailView.as_view(),  name="report-detail"),
]
