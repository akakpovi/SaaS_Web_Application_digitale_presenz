import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_free_subscription(sender, instance, created: bool, **kwargs) -> None:
    """Auto-create a Free subscription when a User is created."""
    if not created:
        return
    from subscriptions.models import Plan, Subscription
    try:
        free_plan = Plan.objects.get(tier=Plan.Tier.FREE)
        _, was_created = Subscription.objects.get_or_create(
            user=instance,
            defaults={"plan": free_plan, "status": Subscription.Status.ACTIVE},
        )
        if was_created:
            logger.info("Free subscription created for user %s", instance.email)
    except Plan.DoesNotExist:
        logger.warning("Free plan not found — subscription not created for %s", instance.email)
