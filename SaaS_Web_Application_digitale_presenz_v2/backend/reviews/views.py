from django.db.models import Avg, Count, Max, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from websites.models import Website
from reviews.models import ResponseDraft, Review, ReviewSource, ReviewImportJob
from reviews.serializers import (
    ResponseDraftSerializer,
    ReviewCreateSerializer,
    ReviewSerializer,
    ReviewSourceSerializer,
    ReviewImportJobSerializer,
)
from reviews.services.responses import generate_draft
from reviews.tasks import analyze_review_sentiment, sync_review_source, process_review_import
from reviews.services.real_discovery import RealReviewDiscoveryService


class ReviewSummaryView(APIView):
    """GET /api/v1/reviews/summary/ — real reputation KPIs."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        reviews = Review.objects.filter(source__user=request.user)
        aggregates = reviews.aggregate(
            average=Avg("rating"),
            last_created=Max("created_at"),
        )
        month_start = timezone.now().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        needs_response = reviews.filter(
            Q(sentiment__in=[Review.Sentiment.NEGATIVE, Review.Sentiment.NEUTRAL])
            | Q(rating__lte=3),
            response_draft__isnull=True,
        ).count()
        by_platform = {
            row["source__provider"]: row["count"]
            for row in reviews.values("source__provider").annotate(count=Count("id"))
        }
        sources = ReviewSource.objects.filter(user=request.user)
        latest_sync = sources.aggregate(last=Max("last_synced_at"))["last"]

        return Response(
            {
                "total": reviews.count(),
                "average_rating": (
                    round(float(aggregates["average"]), 1)
                    if aggregates["average"] is not None
                    else None
                ),
                "new_this_month": reviews.filter(created_at__gte=month_start).count(),
                "needs_response": needs_response,
                "by_platform": by_platform,
                "sources": sources.count(),
                "enabled_sources": sources.filter(enabled=True).count(),
                "last_synced_at": latest_sync.isoformat() if latest_sync else None,
                "latest_review_at": (
                    aggregates["last_created"].isoformat()
                    if aggregates["last_created"]
                    else None
                ),
            }
        )


class ReviewDraftResponseView(APIView):
    """POST /api/v1/reviews/<uuid:pk>/draft-response/

    Generates (or refreshes) the single editable draft for a review.  The
    draft is stored, never sent: publishing remains a human action.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk) -> Response:
        review = get_object_or_404(Review, pk=pk, source__user=request.user)
        draft = generate_draft(review)
        return Response(ResponseDraftSerializer(draft).data, status=status.HTTP_201_CREATED)


class DiscoverRealReviewsView(APIView):
    """Scanne et extrait automatiquement les avis réels du web pour un site donné."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        website_id = request.data.get("website_id")
        if website_id:
            website = get_object_or_404(Website, id=website_id, owner=request.user)
        else:
            website = Website.objects.filter(owner=request.user).first()

        if not website:
            return Response(
                {"error": "Aucun site web trouvé. Ajoutez d'abord un site dans 'Websites'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        discovery_service = RealReviewDiscoveryService(website)
        result = discovery_service.discover_all()
        return Response(result, status=status.HTTP_200_OK)


class ReviewSourceListCreateView(generics.ListCreateAPIView):
    serializer_class   = ReviewSourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ReviewSource.objects.filter(user=self.request.user).select_related("website")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReviewSourceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class   = ReviewSourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ReviewSource.objects.filter(user=self.request.user)


class ReviewListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ReviewCreateSerializer
        return ReviewSerializer

    def get_queryset(self):
        qs = Review.objects.filter(source__user=self.request.user).select_related("source")
        if source_id := self.request.query_params.get("source_id"):
            qs = qs.filter(source_id=source_id)
        if approved := self.request.query_params.get("approved"):
            qs = qs.filter(is_approved=approved.lower() == "true")
        if sentiment := self.request.query_params.get("sentiment"):
            qs = qs.filter(sentiment=sentiment)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class ReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class   = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Review.objects.filter(source__user=self.request.user)


class ApproveReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk) -> Response:
        review = get_object_or_404(Review, pk=pk, source__user=request.user)
        review.is_approved = True
        review.save(update_fields=["is_approved", "updated_at"])
        analyze_review_sentiment.delay(str(review.id))
        return Response(ReviewSerializer(review).data)


class ResponseDraftListCreateView(generics.ListCreateAPIView):
    serializer_class   = ResponseDraftSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ResponseDraft.objects.filter(user=self.request.user).select_related("review")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ResponseDraftDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class   = ResponseDraftSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ResponseDraft.objects.filter(user=self.request.user)


class AnalyzeSentimentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        review = get_object_or_404(Review, id=pk, source__user=request.user)
        task = analyze_review_sentiment.delay(str(review.id))
        return Response({"status": "queued", "task_id": task.id}, status=status.HTTP_202_ACCEPTED)


class SyncReviewSourceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        source = get_object_or_404(ReviewSource, id=pk, user=request.user)
        task = sync_review_source.delay(source.id)
        return Response({"status": "queued", "task_id": task.id}, status=status.HTTP_202_ACCEPTED)


class ReviewBulkImportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        source_id = request.data.get("source_id")
        file_obj = request.FILES.get("file")
        file_type = request.data.get("file_type", "csv")
        if not source_id or not file_obj:
            return Response({"error": "source_id and file are required"}, status=status.HTTP_400_BAD_REQUEST)
        source = get_object_or_404(ReviewSource, id=source_id, user=request.user)
        job = ReviewImportJob.objects.create(user=request.user, source=source, file=file_obj, file_type=file_type)
        process_review_import.delay(str(job.id))
        return Response(ReviewImportJobSerializer(job).data, status=status.HTTP_201_CREATED)


class ReviewImportJobDetailView(generics.RetrieveAPIView):
    serializer_class = ReviewImportJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ReviewImportJob.objects.filter(user=self.request.user)
