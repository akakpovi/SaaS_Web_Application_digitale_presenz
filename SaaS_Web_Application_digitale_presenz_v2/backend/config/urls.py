from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("core.urls")),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/users/", include("accounts.profile_urls")),
    path("api/v1/public/", include("public_checker.urls")),
    path("api/v1/", include("organizations.urls")),
    path("api/v1/", include("integrations.urls")),
    path("api/v1/", include("websites.urls")),
    path("api/v1/", include("scans.urls")),
    path("api/v1/", include("monitoring.urls")),
    path("api/v1/", include("alerts.urls")),
    path("api/v1/", include("notifications.urls")),
    path("api/v1/", include("reports.urls")),
    path("api/v1/", include("reviews.urls")),
    path("api/v1/", include("subscriptions.urls")),
    path("api/v1/", include("seo.urls")),
    path("api/v1/", include("social.urls")),
    path("api/v1/", include("advanced_security.urls")),
    path("api/v1/", include("advisory.urls")),
    path("api/v1/analytics/", include("analytics.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="openapi-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="openapi-schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="openapi-schema"),
        name="redoc",
    ),
]
