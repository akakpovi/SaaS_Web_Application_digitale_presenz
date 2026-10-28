from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from websites.models import Website
from advanced_security.models import SecurityIncident
from advanced_security.serializers import SecurityIncidentSerializer
from advanced_security.tasks import run_security_scan

class SecurityIncidentListView(generics.ListAPIView):
    serializer_class = SecurityIncidentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SecurityIncident.objects.filter(website_id=self.kwargs["website_id"], website__owner=self.request.user)

class TriggerSecurityScanView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, website_id: int):
        from subscriptions.services.quotas import assert_paid_plan

        assert_paid_plan(request.user)
        get_object_or_404(Website, id=website_id, owner=request.user)
        task = run_security_scan.delay(website_id)
        return Response({"status": "queued", "task_id": task.id}, status=202)
