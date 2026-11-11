from django.shortcuts import get_object_or_404
from rest_framework import filters, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from alerts.models import Alert, AlertPreference, AlertRule, MuteWindow
from alerts.serializers import (
    AlertPreferenceSerializer,
    AlertRuleSerializer,
    AlertSerializer,
    MuteWindowSerializer,
)


class AlertListView(generics.ListAPIView):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at", "severity", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Alert.objects.filter(user=self.request.user).select_related("website")
        params = self.request.query_params
        if v := params.get("status"):
            qs = qs.filter(status=v)
        if v := params.get("severity"):
            qs = qs.filter(severity=v)
        if v := params.get("alert_type"):
            qs = qs.filter(alert_type=v)
        if v := params.get("website_id"):
            qs = qs.filter(website_id=v)
        return qs


class AlertDetailView(generics.RetrieveAPIView):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user)


class AcknowledgeAlertView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk) -> Response:
        alert = get_object_or_404(Alert, pk=pk, user=request.user)
        if alert.status != Alert.Status.FIRING:
            return Response(
                {"detail": f"Alert is already {alert.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        alert.acknowledge(request.user)
        return Response(AlertSerializer(alert).data)


class ResolveAlertView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk) -> Response:
        alert = get_object_or_404(Alert, pk=pk, user=request.user)
        if alert.status == Alert.Status.RESOLVED:
            return Response(
                {"detail": "Alert is already resolved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        alert.resolve()
        return Response(AlertSerializer(alert).data)


class AlertPreferenceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        prefs, _ = AlertPreference.objects.get_or_create(user=request.user)
        return Response(AlertPreferenceSerializer(prefs).data)

    def put(self, request) -> Response:
        prefs, _ = AlertPreference.objects.get_or_create(user=request.user)
        serializer = AlertPreferenceSerializer(prefs, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data)

    def patch(self, request) -> Response:
        prefs, _ = AlertPreference.objects.get_or_create(user=request.user)
        serializer = AlertPreferenceSerializer(prefs, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data)


class AlertRuleListCreateView(generics.ListCreateAPIView):
    serializer_class = AlertRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AlertRule.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AlertRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AlertRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AlertRule.objects.filter(user=self.request.user)


class MuteWindowListCreateView(generics.ListCreateAPIView):
    serializer_class = MuteWindowSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MuteWindow.objects.filter(user=self.request.user).prefetch_related(
            "websites"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class MuteWindowDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = MuteWindowSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MuteWindow.objects.filter(user=self.request.user)
