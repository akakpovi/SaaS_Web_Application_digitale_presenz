import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Sum
from django.contrib.auth import get_user_model
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import TrafficLog, AnalyticsEvent, AffiliateClick
from subscriptions.models import Plan, Subscription
from websites.models import Website
from scans.models import Scan

User = get_user_model()
logger = logging.getLogger(__name__)


class TrackEventPublicView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        event_type = request.data.get("event_type", "page_view")
        metadata = request.data.get("metadata", {})
        user = request.user if request.user.is_authenticated else None

        AnalyticsEvent.objects.create(
            user=user,
            event_type=str(event_type),
            metadata=metadata if isinstance(metadata, dict) else {},
        )
        return Response({"status": "tracked"}, status=status.HTTP_201_CREATED)


class AdminDashboardAnalyticsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        fourteen_days_ago = now - timedelta(days=14)

        total_users = User.objects.count()
        total_websites = Website.objects.count()
        total_scans = Scan.objects.count()
        total_visitors = (
            TrafficLog.objects.filter(is_bot=False).values("ip_hash").distinct().count()
        )

        daily_traffic = (
            TrafficLog.objects.filter(created_at__gte=fourteen_days_ago)
            .extra(select={"day": "DATE(created_at)"})
            .values("day")
            .annotate(views=Count("id"), uniques=Count("ip_hash", distinct=True))
            .order_by("day")
        )

        signups = AnalyticsEvent.objects.filter(
            event_type="signup", created_at__gte=thirty_days_ago
        ).count()
        added_sites = AnalyticsEvent.objects.filter(
            event_type="add_website", created_at__gte=thirty_days_ago
        ).count()
        scans_run = AnalyticsEvent.objects.filter(
            event_type__in=["trigger_scan", "public_check"],
            created_at__gte=thirty_days_ago,
        ).count()

        cookie_accept = AnalyticsEvent.objects.filter(
            event_type="cookie_accept", created_at__gte=thirty_days_ago
        ).count()
        cookie_essential = AnalyticsEvent.objects.filter(
            event_type="cookie_essential", created_at__gte=thirty_days_ago
        ).count()

        total_pageviews = TrafficLog.objects.filter(
            is_bot=False, created_at__gte=thirty_days_ago
        ).count()
        ad_revenue = (total_pageviews / 1000.0) * 2.5
        affiliate_revenue = (
            AffiliateClick.objects.filter(converted=True).aggregate(
                s=Sum("commission_eur")
            )["s"]
            or 0.0
        )

        monetization_index = min(
            100,
            int((total_pageviews * 0.4) + (total_websites * 0.3) + (total_users * 0.3)),
        )

        # Real recurring revenue: active, paid subscriptions only (trial users
        # pay nothing yet, so they are counted separately).  A yearly plan is
        # normalised to its monthly equivalent so MRR stays comparable.
        paid_subscriptions = (
            Subscription.objects.filter(
                status=Subscription.Status.ACTIVE,
            )
            .exclude(plan__tier=Plan.Tier.FREE)
            .select_related("plan")
        )
        trialing = (
            Subscription.objects.filter(
                status=Subscription.Status.TRIALING,
            )
            .exclude(plan__tier=Plan.Tier.FREE)
            .count()
        )

        mrr = 0.0
        by_plan: dict[str, dict] = {}
        for subscription in paid_subscriptions:
            plan = subscription.plan
            if subscription.billing_cycle == Subscription.BillingCycle.YEARLY:
                monthly = float(plan.price_yearly) / 12
            else:
                monthly = float(plan.price_monthly)
            mrr += monthly
            entry = by_plan.setdefault(
                plan.tier,
                {"tier": plan.tier, "name": plan.name, "count": 0, "mrr_eur": 0.0},
            )
            entry["count"] += 1
            entry["mrr_eur"] += monthly

        for entry in by_plan.values():
            entry["mrr_eur"] = round(entry["mrr_eur"], 2)

        paying_users = paid_subscriptions.count()

        return Response(
            {
                "overview": {
                    "total_users": total_users,
                    "total_websites": total_websites,
                    "total_scans": total_scans,
                    "total_visitors": total_visitors,
                    "monetization_index": monetization_index,
                },
                "traffic_14d": list(daily_traffic),
                "funnel": {
                    "signups": signups,
                    "added_websites": added_sites,
                    "scans_triggered": scans_run,
                },
                "cookies": {
                    "accepted_all": cookie_accept,
                    "essential_only": cookie_essential,
                },
                "subscriptions": {
                    "mrr_eur": round(mrr, 2),
                    "arr_eur": round(mrr * 12, 2),
                    "paying_users": paying_users,
                    "trialing_users": trialing,
                    "by_plan": sorted(
                        by_plan.values(),
                        key=lambda entry: entry["mrr_eur"],
                        reverse=True,
                    ),
                },
                "estimated_revenue": {
                    "ads_eur": round(ad_revenue, 2),
                    "affiliate_eur": float(affiliate_revenue),
                    "total_eur": round(ad_revenue + float(affiliate_revenue), 2),
                },
                "latest_users": [
                    {
                        "id": u.id,
                        "email": u.email,
                        "created_at": u.date_joined.isoformat()
                        if hasattr(u, "date_joined") and u.date_joined
                        else None,
                        "websites_count": u.websites.count()
                        if hasattr(u, "websites")
                        else 0,
                    }
                    for u in User.objects.order_by("-id")[:5]
                ],
            },
            status=status.HTTP_200_OK,
        )
