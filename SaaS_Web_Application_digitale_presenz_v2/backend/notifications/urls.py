from django.urls import path
from notifications.views import (
    NotificationChannelDetailView,
    NotificationChannelListCreateView,
    TestNotificationChannelView,
    SubscribePushView,
    TestPushNotificationView,
)

urlpatterns = [
    path("notifications/channels/", NotificationChannelListCreateView.as_view(), name="notification-channel-list"),
    path("notifications/channels/<int:pk>/", NotificationChannelDetailView.as_view(), name="notification-channel-detail"),
    path("notifications/channels/<int:pk>/test/", TestNotificationChannelView.as_view(), name="notification-channel-test"),
    
    # Routes Web Push PWA & Test en direct
    path("notifications/push/subscribe/", SubscribePushView.as_view(), name="push-subscribe"),
    path("notifications/push/test/", TestPushNotificationView.as_view(), name="push-test"),
]
