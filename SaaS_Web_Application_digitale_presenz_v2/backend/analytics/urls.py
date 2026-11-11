from django.urls import path
from .views import AdminDashboardAnalyticsView, TrackEventPublicView

urlpatterns = [
    path(
        "admin/overview/",
        AdminDashboardAnalyticsView.as_view(),
        name="admin-analytics-overview",
    ),
    path("events/track/", TrackEventPublicView.as_view(), name="analytics-track-event"),
]
