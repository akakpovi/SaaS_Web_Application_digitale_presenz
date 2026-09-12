import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="notifications.send_public_scan_report_email",
)
def send_public_scan_report_email(self, lead_id: int, scan_id: int, email: str, language_code: str = "en"):
    from public_checker.models import PublicLead
    from scans.models import Scan

    try:
        scan = (
            Scan.objects
            .select_related("website")
            .prefetch_related("check_results")
            .get(id=scan_id)
        )
    except Scan.DoesNotExist:
        logger.error("send_public_scan_report_email: Scan %s introuvable.", scan_id)
        return

    lead = PublicLead.objects.filter(id=lead_id).first()

    supported_languages = {code for code, _label in getattr(settings, "LANGUAGES", [("fr", "Français"), ("en", "English"), ("de", "Deutsch")])}
    if language_code not in supported_languages:
        language_code = settings.LANGUAGE_CODE.split("-")[0]

    with translation.override(language_code):
        subject = _("Votre rapport de présence digitale — %(domain)s") % {
            "domain": scan.website.domain,
        }
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost")
        html_content = render_to_string(
            "emails/public_scan_report.html",
            {
                "scan": scan,
                "website": scan.website,
                "checks": scan.check_results.all(),
                "score": scan.health_score,
                "cta_url": f"{frontend_url}/register?scan_id={scan.id}&url={scan.website.domain}",
            },
        )

    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body="",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        message.attach_alternative(html_content, "text/html")
        message.send(fail_silently=False)

        if lead:
            lead.email_sent = True
            lead.save(update_fields=["email_sent"])

        logger.info("✅ Rapport envoyé à %s (langue=%s, scan=%s)", email, language_code, scan_id)
    except Exception as exc:
        logger.warning("⚠️ Échec envoi rapport à %s : %s", email, exc)
        raise self.retry(exc=exc)
