from django.urls import path

from subscriptions.api_views import ApiKeyListCreateView, ApiKeyRevokeView
from subscriptions.views import (
    CancelSubscriptionView,
    CheckoutView,
    PaddleWebhookView,
    PlanListView,
    PortalView,
    SubscriptionView,
    UpgradeSubscriptionView,
)

urlpatterns = [
    path("subscriptions/plans/", PlanListView.as_view(), name="plan-list"),
    path("subscriptions/me/", SubscriptionView.as_view(), name="subscription-me"),
    path("subscriptions/checkout/", CheckoutView.as_view(), name="subscription-checkout"),
    path("subscriptions/portal/", PortalView.as_view(), name="subscription-portal"),
    path("subscriptions/upgrade/", UpgradeSubscriptionView.as_view(), name="subscription-upgrade"),
    path("subscriptions/cancel/", CancelSubscriptionView.as_view(), name="subscription-cancel"),
    path("webhooks/paddle/", PaddleWebhookView.as_view(), name="paddle-webhook"),
    path("api-keys/", ApiKeyListCreateView.as_view(), name="api-key-list"),
    path("api-keys/<uuid:pk>/", ApiKeyRevokeView.as_view(), name="api-key-revoke"),
]
