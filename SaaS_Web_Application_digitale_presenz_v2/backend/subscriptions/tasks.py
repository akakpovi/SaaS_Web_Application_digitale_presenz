"""Subscription lifecycle maintenance.

Billing providers are not guaranteed to deliver every event (a webhook can be
lost while the endpoint is down).  A subscription whose paid period ended must
stop granting the paid tier even when the ``subscription.canceled`` or
``transaction.payment_failed`` event never arrived, so this daily task closes
the gap: the row is marked EXPIRED and the effective plan falls back to Free
through :func:`subscriptions.services.quotas.get_effective_plan`.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="subscriptions.tasks.expire_subscriptions")
def expire_subscriptions() -> dict:
    from subscriptions.models import Subscription

    now = timezone.now()
    stale = Subscription.objects.filter(
        current_period_end__isnull=False,
        current_period_end__lte=now,
        status__in=(
            Subscription.Status.ACTIVE,
            Subscription.Status.TRIALING,
            Subscription.Status.PAST_DUE,
            Subscription.Status.CANCELLED,
        ),
    )
    expired = 0
    for sub in stale.iterator():
        sub.status = Subscription.Status.EXPIRED
        sub.save(update_fields=["status", "updated_at"])
        expired += 1
        logger.info(
            "Subscription %s expired (user=%s, period_end=%s)",
            sub.pk,
            sub.user_id,
            sub.current_period_end,
        )

    return {"expired": expired}
