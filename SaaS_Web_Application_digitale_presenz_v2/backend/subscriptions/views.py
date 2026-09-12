from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from subscriptions.models import Plan, Subscription
from subscriptions.serializers import (
    PlanSerializer,
    SubscriptionSerializer,
    UpgradeSubscriptionSerializer,
)


class PlanListView(generics.ListAPIView):
    """GET /api/v1/subscriptions/plans/ — public endpoint"""
    serializer_class   = PlanSerializer
    permission_classes = [permissions.AllowAny]
    queryset           = Plan.objects.filter(is_active=True)


class SubscriptionView(APIView):
    """GET /api/v1/subscriptions/me/"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        try:
            sub = request.user.subscription
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(SubscriptionSerializer(sub).data)


class UpgradeSubscriptionView(APIView):
    """
    POST /api/v1/subscriptions/upgrade/
    Provider-independent: just updates the plan.
    Real billing integration can be added later.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request) -> Response:
        serializer = UpgradeSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            plan = Plan.objects.get(tier=data["plan_tier"], is_active=True)
        except Plan.DoesNotExist:
            return Response(
                {"detail": "Plan not found or not available."},
                status=status.HTTP_404_NOT_FOUND,
            )

        sub, _ = Subscription.objects.get_or_create(
            user=request.user,
            defaults={"plan": plan},
        )
        sub.plan          = plan
        sub.billing_cycle = data["billing_cycle"]
        sub.status        = Subscription.Status.ACTIVE
        sub.save(update_fields=["plan", "billing_cycle", "status", "updated_at"])

        return Response(SubscriptionSerializer(sub).data)


class CancelSubscriptionView(APIView):
    """POST /api/v1/subscriptions/cancel/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request) -> Response:
        try:
            sub = request.user.subscription
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if sub.is_free:
            return Response(
                {"detail": "Cannot cancel a free subscription."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sub.cancel()
        return Response(SubscriptionSerializer(sub).data)
