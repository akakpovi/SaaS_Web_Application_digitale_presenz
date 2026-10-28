import json
import logging

from django.conf import settings
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from subscriptions.models import BillingEvent, Plan, Subscription
from subscriptions.serializers import (
    CheckoutSerializer,
    PlanSerializer,
    SubscriptionSerializer,
    UpgradeSubscriptionSerializer,
)
from subscriptions.services import billing, quotas

logger = logging.getLogger(__name__)


class PlanListView(generics.ListAPIView):
    """GET /api/v1/subscriptions/plans/ — public endpoint"""

    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    queryset = Plan.objects.filter(is_active=True)


class SubscriptionView(APIView):
    """GET /api/v1/subscriptions/me/"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        try:
            sub = request.user.subscription
        except Subscription.DoesNotExist:
            # Accounts created before the plan catalogue was seeded have no
            # subscription row.  Provision the Free plan on first read instead
            # of returning a 404 that leaves the billing page broken.
            free_plan = quotas.get_free_plan()
            if free_plan is None:
                return Response(
                    {
                        "detail": "No subscription found.",
                        "billing": {
                            "enabled": billing.is_configured(),
                            "provider": billing.get_provider(),
                        },
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            sub, _ = Subscription.objects.get_or_create(
                user=request.user,
                defaults={"plan": free_plan},
            )

        data = SubscriptionSerializer(sub).data
        data["billing"] = {
            "enabled": billing.is_configured(),
            "provider": billing.get_provider(),
            "customer_id": (sub.billing_metadata or {}).get("customer_id"),
            "cancel_at_period_end": bool(
                (sub.billing_metadata or {}).get("cancel_at_period_end")
            ),
        }
        data.update(quotas.plan_snapshot(request.user))
        return Response(data)


class CheckoutView(APIView):
    """POST /api/v1/subscriptions/checkout/

    Body: ``{"plan_tier": "pro|business|agency", "billing_cycle": "monthly|yearly"}``.
    Returns the provider-hosted checkout URL.  The client never sends an amount.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request) -> Response:
        if not billing.is_configured():
            return Response(
                {
                    "detail": "Billing is not configured. Checkout is disabled.",
                    "code": "billing_not_configured",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        plan = Plan.objects.filter(
            tier=data["plan_tier"], is_active=True
        ).first()
        if plan is None or plan.tier == Plan.Tier.FREE:
            return Response(
                {
                    "detail": "This plan is not available for checkout.",
                    "code": "plan_not_available",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            checkout = billing.create_checkout(
                request.user, plan, data["billing_cycle"]
            )
        except billing.BillingNotConfigured as exc:
            return Response(
                {"detail": str(exc), "code": "billing_not_configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except billing.BillingProviderError as exc:
            return Response(
                {"detail": str(exc), "code": "billing_provider_error"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(checkout, status=status.HTTP_201_CREATED)


class PortalView(APIView):
    """POST /api/v1/subscriptions/portal/ — customer portal URL."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request) -> Response:
        if not billing.is_configured():
            return Response(
                {
                    "detail": "Billing is not configured.",
                    "code": "billing_not_configured",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            url = billing.create_portal_session(request.user)
        except billing.BillingNotConfigured as exc:
            return Response(
                {"detail": str(exc), "code": "no_billing_account"},
                status=status.HTTP_409_CONFLICT,
            )
        except billing.BillingProviderError as exc:
            return Response(
                {"detail": str(exc), "code": "billing_provider_error"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({"portal_url": url})


class UpgradeSubscriptionView(APIView):
    """POST /api/v1/subscriptions/upgrade/ — legacy, now closed.

    Plan changes only happen through the payment provider webhook after a
    captured payment.  This endpoint must never grant a paid plan, whether
    billing is configured or not.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request) -> Response:
        if not billing.is_configured(require_api_key=False):
            return Response(
                {
                    "detail": "Billing is not configured. Plan changes are disabled.",
                    "code": "billing_not_configured",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Validate the payload so clients get a useful error, then refuse.
        UpgradeSubscriptionSerializer(data=request.data).is_valid(
            raise_exception=True
        )
        return Response(
            {
                "detail": "Use /subscriptions/checkout/ to change plan. "
                "Plans are activated by the payment webhook.",
                "code": "use_checkout",
            },
            status=status.HTTP_409_CONFLICT,
        )


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

        if billing.is_configured() and sub.external_id:
            try:
                billing.cancel_at_period_end(sub)
            except billing.BillingNotConfigured:
                pass
            except billing.BillingProviderError as exc:
                return Response(
                    {"detail": str(exc), "code": "billing_provider_error"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            sub.refresh_from_db()
            return Response(
                {
                    "detail": "Subscription will end at the end of the paid period.",
                    "subscription": SubscriptionSerializer(sub).data,
                }
            )

        sub.cancel()
        return Response(SubscriptionSerializer(sub).data)


class PaddleWebhookView(APIView):
    """POST /api/v1/webhooks/paddle/

    Public by design (the provider cannot send a JWT), authenticated by the
    ``Paddle-Signature`` HMAC, and idempotent on ``event_id``.  A replayed
    event never applies a second plan change.
    """

    authentication_classes: list = []
    permission_classes = [permissions.AllowAny]
    throttle_classes: list = []

    def post(self, request) -> Response:
        if not billing.is_configured(require_api_key=False):
            return Response(
                {"detail": "Billing is not configured.", "code": "billing_not_configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        secret = getattr(settings, "PADDLE_WEBHOOK_SECRET", "")
        if not secret:
            logger.error("Paddle webhook received but PADDLE_WEBHOOK_SECRET is unset")
            return Response(
                {"detail": "Webhook secret is not configured.", "code": "webhook_not_configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        signature = request.headers.get("Paddle-Signature", "")
        if not billing.verify_paddle_signature(request.body, signature, secret):
            logger.warning("Rejected Paddle webhook with invalid signature")
            return Response(
                {"detail": "Invalid signature.", "code": "invalid_signature"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = json.loads(request.body)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Invalid JSON body.", "code": "invalid_payload"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        event_id = payload.get("event_id")
        event_type = payload.get("event_type", "")
        data = payload.get("data") or {}
        if not event_id or not event_type:
            return Response(
                {"detail": "Missing event_id or event_type.", "code": "invalid_payload"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        event, created = BillingEvent.objects.get_or_create(
            provider="paddle",
            event_id=event_id,
            defaults={
                "event_type": event_type,
                "payload": payload,
                "status": BillingEvent.Status.RECEIVED,
            },
        )

        if not created and event.status == BillingEvent.Status.PROCESSED:
            logger.info("Paddle webhook %s already processed — ignored", event_id)
            return Response({"status": "duplicate", "event_id": event_id})

        try:
            result = billing.process_paddle_event(event_type, data)
        except billing.BillingError as exc:
            event.status = BillingEvent.Status.FAILED
            event.error = str(exc)[:2000]
            event.save(update_fields=["status", "error"])
            logger.exception("Paddle webhook %s failed: %s", event_id, exc)
            # 500 lets Paddle retry once the price/plan mapping is fixed.
            return Response(
                {"detail": "Webhook processing failed.", "code": "processing_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        event.status = BillingEvent.Status.PROCESSED
        event.processed_at = timezone.now()
        event.error = ""
        event.event_type = event_type
        event.payload = payload
        event.save(
            update_fields=["status", "processed_at", "error", "event_type", "payload"]
        )

        return Response({"status": "processed", "event_id": event_id, "result": result})
