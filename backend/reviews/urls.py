from django.urls import path

from reviews.views import (
    ApproveReviewView,
    ResponseDraftDetailView,
    ResponseDraftListCreateView,
    ReviewDetailView,
    ReviewListCreateView,
    ReviewSourceDetailView,
    ReviewSourceListCreateView,
)

urlpatterns = [
    path("reviews/sources/",              ReviewSourceListCreateView.as_view(), name="review-source-list"),
    path("reviews/sources/<int:pk>/",     ReviewSourceDetailView.as_view(),     name="review-source-detail"),
    path("reviews/",                      ReviewListCreateView.as_view(),        name="review-list"),
    path("reviews/<uuid:pk>/",            ReviewDetailView.as_view(),            name="review-detail"),
    path("reviews/<uuid:pk>/approve/",    ApproveReviewView.as_view(),           name="review-approve"),
    path("reviews/responses/",            ResponseDraftListCreateView.as_view(), name="response-draft-list"),
    path("reviews/responses/<int:pk>/",   ResponseDraftDetailView.as_view(),     name="response-draft-detail"),
]
