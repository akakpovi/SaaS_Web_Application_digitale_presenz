from django.urls import path

from .views import (
    OAuthAuthorizeView,
    OAuthCallbackView,
    OAuthConnectionDetailView,
    OAuthConnectionListView,
    SocialAuditEventListView,
)

app_name = "integrations"

urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/social/audit/",
        SocialAuditEventListView.as_view(),
        name="social-audit",
    ),
    path(
        "organizations/<uuid:organization_id>/social/connections/",
        OAuthConnectionListView.as_view(),
        name="oauth-connections",
    ),
    path(
        "organizations/<uuid:organization_id>/social/connections/"
        "<uuid:connection_id>/",
        OAuthConnectionDetailView.as_view(),
        name="oauth-connection-detail",
    ),
    path(
        "organizations/<uuid:organization_id>/social/connections/"
        "<str:provider>/authorize/",
        OAuthAuthorizeView.as_view(),
        name="oauth-authorize",
    ),
    path(
        "social/oauth/<str:provider>/callback/",
        OAuthCallbackView.as_view(),
        name="oauth-callback",
    ),
]
