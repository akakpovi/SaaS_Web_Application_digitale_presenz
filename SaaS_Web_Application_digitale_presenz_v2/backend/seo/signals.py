import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from websites.models import Website
logger = logging.getLogger(__name__)

@receiver(post_save, sender=Website)
def trigger_initial_seo_scan(sender, instance, created, **kwargs):
    if not created: return
    from seo.tasks import run_seo_audit
    run_seo_audit.delay(instance.id)
    logger.info("Initial SEO scan for %s", instance.domain)
