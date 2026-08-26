from django.urls import path

from notifications.views import (
    NotificationChannelDetailView,
    NotificationChannelListCreateView,
    TestNotificationChannelView,
)

urlpatterns = [
    path("notifications/channels/", NotificationChannelListCreateView.as_view(), name="notification-channel-list"),
    path("notifications/channels/<int:pk>/", NotificationChannelDetailView.as_view(), name="notification-channel-detail"),
    path("notifications/channels/<int:pk>/test/", TestNotificationChannelView.as_view(), name="notification-channel-test"),
]
