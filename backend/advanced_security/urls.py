from django.urls import path
from advanced_security.views import SecurityIncidentListView, TriggerSecurityScanView

urlpatterns = [
    path("websites/<int:website_id>/security/incidents/", SecurityIncidentListView.as_view(), name="security-incidents"),
    path("websites/<int:website_id>/security/scan/", TriggerSecurityScanView.as_view(), name="security-scan-trigger"),
]
