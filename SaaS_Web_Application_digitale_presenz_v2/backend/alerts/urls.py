from django.urls import path

from alerts.views import (
    AcknowledgeAlertView,
    AlertDetailView,
    AlertListView,
    AlertPreferenceView,
    AlertRuleDetailView,
    AlertRuleListCreateView,
    MuteWindowDetailView,
    MuteWindowListCreateView,
    ResolveAlertView,
)

urlpatterns = [
    path("alerts/", AlertListView.as_view(), name="alert-list"),
    path(
        "alerts/preferences/", AlertPreferenceView.as_view(), name="alert-preferences"
    ),
    path("alerts/rules/", AlertRuleListCreateView.as_view(), name="alert-rule-list"),
    path(
        "alerts/rules/<int:pk>/",
        AlertRuleDetailView.as_view(),
        name="alert-rule-detail",
    ),
    path(
        "alerts/mute-windows/",
        MuteWindowListCreateView.as_view(),
        name="mute-window-list",
    ),
    path(
        "alerts/mute-windows/<int:pk>/",
        MuteWindowDetailView.as_view(),
        name="mute-window-detail",
    ),
    path("alerts/<uuid:pk>/", AlertDetailView.as_view(), name="alert-detail"),
    path(
        "alerts/<uuid:pk>/acknowledge/",
        AcknowledgeAlertView.as_view(),
        name="alert-acknowledge",
    ),
    path("alerts/<uuid:pk>/resolve/", ResolveAlertView.as_view(), name="alert-resolve"),
]
