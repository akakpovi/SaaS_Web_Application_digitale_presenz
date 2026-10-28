from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from websites.models import Website
from seo.models import SEOAudit, Keyword, Backlink
from seo.serializers import SEOAuditSerializer, KeywordSerializer, BacklinkSerializer
from seo.tasks import run_seo_audit

class SEOAuditListView(generics.ListAPIView):
    serializer_class = SEOAuditSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SEOAudit.objects.filter(website_id=self.kwargs["website_id"], website__owner=self.request.user)

class TriggerSEOAuditView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, website_id: int):
        from subscriptions.services.quotas import assert_paid_plan

        assert_paid_plan(request.user)
        website = get_object_or_404(Website, id=website_id, owner=request.user)
        task = run_seo_audit.delay(website.id)
        return Response({"status": "queued", "task_id": task.id}, status=202)

class KeywordListCreateView(generics.ListCreateAPIView):
    serializer_class = KeywordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Keyword.objects.filter(website_id=self.kwargs["website_id"], website__owner=self.request.user)

    def perform_create(self, serializer):
        website = get_object_or_404(Website, id=self.kwargs["website_id"], owner=self.request.user)
        serializer.save(website=website)

class BacklinkListView(generics.ListAPIView):
    serializer_class = BacklinkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Backlink.objects.filter(website_id=self.kwargs["website_id"], website__owner=self.request.user)
