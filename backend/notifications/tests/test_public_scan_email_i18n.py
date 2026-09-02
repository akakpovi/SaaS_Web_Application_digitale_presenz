from unittest.mock import patch
from django.core import mail
from django.test import TestCase
from django.utils import translation

from websites.models import Website
from scans.models import Scan
from public_checker.models import PublicLead
from notifications.tasks import send_public_scan_report_email


class PublicScanEmailI18nTests(TestCase):
    def setUp(self):
        self.website = Website.objects.create(domain="exemple-i18n.com", is_guest=True)
        self.scan = Scan.objects.create(
            website=self.website, status="completed", health_score=82, is_guest=True,
        )
        self.lead = PublicLead.objects.create(
            email="lead-i18n@example.com", url_scanned=f"https://{self.website.domain}", scan_id=str(self.scan.id),
        )

    def _run_with_language(self, language_code):
        captured = {}

        def fake_render(template_name, context=None, request=None, using=None):
            captured["language"] = translation.get_language()
            return "<html><body>Mock Email Content</body></html>"

        with patch("notifications.tasks.render_to_string", side_effect=fake_render):
            send_public_scan_report_email.apply(kwargs={
                "lead_id": self.lead.id,
                "scan_id": self.scan.id,
                "email": self.lead.email,
                "language_code": language_code,
            }).get()

        return captured

    def test_email_rendered_in_german_when_requested(self):
        captured = self._run_with_language("de")
        print("🌍 Langue active pendant le render :", captured.get("language"))
        self.assertEqual(captured.get("language"), "de")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.lead.email, mail.outbox[0].to)

    def test_unsupported_language_falls_back(self):
        captured = self._run_with_language("zz")
        print("🌍 Fallback langue non supportée :", captured.get("language"))
        self.assertIn(captured.get("language"), ("fr", "en"))
