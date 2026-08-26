from django.urls import path

from subscriptions.views import (
    CancelSubscriptionView,
    PlanListView,
    SubscriptionView,
    UpgradeSubscriptionView,
)

urlpatterns = [
    path("subscriptions/plans/",   PlanListView.as_view(),         name="plan-list"),
    path("subscriptions/me/",      SubscriptionView.as_view(),     name="subscription-me"),
    path("subscriptions/upgrade/", UpgradeSubscriptionView.as_view(), name="subscription-upgrade"),
    path("subscriptions/cancel/",  CancelSubscriptionView.as_view(),  name="subscription-cancel"),
]
