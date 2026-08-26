from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from reviews.models import ResponseDraft, Review, ReviewSource
from reviews.serializers import (
    ResponseDraftSerializer,
    ReviewCreateSerializer,
    ReviewSerializer,
    ReviewSourceSerializer,
)


class ReviewSourceListCreateView(generics.ListCreateAPIView):
    """GET / POST /api/v1/reviews/sources/"""
    serializer_class   = ReviewSourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ReviewSource.objects.filter(user=self.request.user).select_related("website")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReviewSourceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET / PUT / PATCH / DELETE /api/v1/reviews/sources/<id>/"""
    serializer_class   = ReviewSourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ReviewSource.objects.filter(user=self.request.user)


class ReviewListCreateView(generics.ListCreateAPIView):
    """GET / POST /api/v1/reviews/"""
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
    """GET / PUT / PATCH / DELETE /api/v1/reviews/<id>/"""
    serializer_class   = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Review.objects.filter(source__user=self.request.user)


class ApproveReviewView(APIView):
    """POST /api/v1/reviews/<id>/approve/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk) -> Response:
        review = get_object_or_404(Review, pk=pk, source__user=request.user)
        review.is_approved = True
        review.save(update_fields=["is_approved", "updated_at"])
        return Response(ReviewSerializer(review).data)


class ResponseDraftListCreateView(generics.ListCreateAPIView):
    """GET / POST /api/v1/reviews/responses/"""
    serializer_class   = ResponseDraftSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ResponseDraft.objects.filter(user=self.request.user).select_related("review")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ResponseDraftDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET / PUT / PATCH / DELETE /api/v1/reviews/responses/<id>/"""
    serializer_class   = ResponseDraftSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ResponseDraft.objects.filter(user=self.request.user)
