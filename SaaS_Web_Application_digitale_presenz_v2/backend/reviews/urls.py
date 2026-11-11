from django.urls import path
from reviews.views import (
    DiscoverRealReviewsView,
    ApproveReviewView,
    ResponseDraftDetailView,
    ResponseDraftListCreateView,
    ReviewDetailView,
    ReviewDraftResponseView,
    ReviewListCreateView,
    ReviewSourceDetailView,
    ReviewSourceListCreateView,
    ReviewSummaryView,
    AnalyzeSentimentView,
    SyncReviewSourceView,
    ReviewBulkImportView,
    ReviewImportJobDetailView,
)

urlpatterns = [
    path(
        "reviews/discover/",
        DiscoverRealReviewsView.as_view(),
        name="reviews-discover-real",
    ),
    path("reviews/summary/", ReviewSummaryView.as_view(), name="reviews-summary"),
    path(
        "reviews/sources/",
        ReviewSourceListCreateView.as_view(),
        name="review-source-list",
    ),
    path(
        "reviews/sources/<int:pk>/",
        ReviewSourceDetailView.as_view(),
        name="review-source-detail",
    ),
    path(
        "reviews/sources/<int:pk>/sync/",
        SyncReviewSourceView.as_view(),
        name="review-source-sync",
    ),
    path("reviews/", ReviewListCreateView.as_view(), name="review-list"),
    path("reviews/<uuid:pk>/", ReviewDetailView.as_view(), name="review-detail"),
    path(
        "reviews/<uuid:pk>/approve/", ApproveReviewView.as_view(), name="review-approve"
    ),
    path(
        "reviews/<uuid:pk>/draft-response/",
        ReviewDraftResponseView.as_view(),
        name="review-draft-response",
    ),
    path(
        "reviews/<uuid:pk>/analyze-sentiment/",
        AnalyzeSentimentView.as_view(),
        name="review-analyze-sentiment",
    ),
    path(
        "reviews/responses/",
        ResponseDraftListCreateView.as_view(),
        name="response-draft-list",
    ),
    path(
        "reviews/responses/<int:pk>/",
        ResponseDraftDetailView.as_view(),
        name="response-draft-detail",
    ),
    path("reviews/import/", ReviewBulkImportView.as_view(), name="review-bulk-import"),
    path(
        "reviews/import/<uuid:pk>/",
        ReviewImportJobDetailView.as_view(),
        name="review-import-job-detail",
    ),
]
