from django.urls import path

from monitoring.views import (
    MonitoringConfigDetailView,
    MonitoringConfigListView,
    TriggerImmediateScanView,
)

urlpatterns = [
    path("monitoring/", MonitoringConfigListView.as_view(), name="monitoring-list"),
    path("monitoring/websites/<int:website_id>/", MonitoringConfigDetailView.as_view(), name="monitoring-detail"),
    path("monitoring/websites/<int:website_id>/scan/", TriggerImmediateScanView.as_view(), name="monitoring-trigger-scan"),
]
