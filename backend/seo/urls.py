from django.urls import path
from seo.views import SEOAuditListView, TriggerSEOAuditView, KeywordListCreateView, BacklinkListView

urlpatterns = [
    path("websites/<int:website_id>/seo/audits/", SEOAuditListView.as_view(), name="seo-audit-list"),
    path("websites/<int:website_id>/seo/audits/run/", TriggerSEOAuditView.as_view(), name="seo-audit-run"),
    path("websites/<int:website_id>/seo/keywords/", KeywordListCreateView.as_view(), name="seo-keywords"),
    path("websites/<int:website_id>/seo/backlinks/", BacklinkListView.as_view(), name="seo-backlinks"),
]
