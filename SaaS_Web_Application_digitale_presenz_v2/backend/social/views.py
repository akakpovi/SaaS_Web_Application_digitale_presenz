from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from websites.models import Website
from social.models import SocialProfile, SocialMention
from social.serializers import SocialProfileSerializer, SocialMentionSerializer
from social.tasks import sync_social_profiles, track_brand_mentions


class SocialProfileListCreateView(generics.ListCreateAPIView):
    serializer_class = SocialProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SocialProfile.objects.filter(
            website_id=self.kwargs["website_id"], website__owner=self.request.user
        )

    def perform_create(self, serializer):
        website = get_object_or_404(
            Website, id=self.kwargs["website_id"], owner=self.request.user
        )
        serializer.save(website=website)


class TriggerSocialSyncView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, website_id: int):
        from subscriptions.services.quotas import assert_paid_plan

        assert_paid_plan(request.user)
        get_object_or_404(Website, id=website_id, owner=request.user)
        sync_social_profiles.delay(website_id)
        track_brand_mentions.delay(website_id)
        return Response({"status": "queued"}, status=202)


class SocialMentionListView(generics.ListAPIView):
    serializer_class = SocialMentionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SocialMention.objects.filter(
            website_id=self.kwargs["website_id"], website__owner=self.request.user
        )
