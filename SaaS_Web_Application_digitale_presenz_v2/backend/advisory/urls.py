from django.urls import path

from .views import (
    asset_scan_report_import,
    asset_security_findings,
    organization_advisor_chat,
    recommendation_accept,
    recommendation_dismiss,
    recommendation_list,
)

urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/assets/<int:asset_id>/scans/import/",
        asset_scan_report_import,
        name="asset-scan-report-import",
    ),
    path(
        "organizations/<uuid:organization_id>/assets/<int:asset_id>/security/findings/",
        asset_security_findings,
        name="asset-security-findings",
    ),
    path(
        "organizations/<uuid:organization_id>/ai-advisor/chat/",
        organization_advisor_chat,
        name="organization-advisor-chat",
    ),
    path(
        "advisory/recommendations/",
        recommendation_list,
        name="advisory-recommendations",
    ),
    path(
        "advisory/recommendations/<uuid:pk>/accept/",
        recommendation_accept,
        {"decision": "accept"},
        name="advisory-recommendation-accept",
    ),
    path(
        "advisory/recommendations/<uuid:pk>/dismiss/",
        recommendation_dismiss,
        {"decision": "dismiss"},
        name="advisory-recommendation-dismiss",
    ),
]
