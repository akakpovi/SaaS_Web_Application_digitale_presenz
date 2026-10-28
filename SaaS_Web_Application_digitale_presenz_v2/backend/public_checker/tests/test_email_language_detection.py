"""
Test d'intégration — Détection Accept-Language

Le scan invité doit appartenir à la session du visiteur (P0-03) : l'endpoint
``/email/`` refuse désormais tout scan d'un autre visiteur ou d'un compte tiers.
"""
import uuid
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from scans.models import Scan
from websites.models import Website


class PublicScanEmailLanguageDetectionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        # Session du visiteur : c'est elle qui autorise l'envoi du rapport.
        session = self.client.session
        session.save()
        self.session_key = session.session_key

        self.website = Website.objects.create(domain="lang-detect.com", is_guest=True)
        self.scan = Scan.objects.create(
            website=self.website,
            status="completed",
            health_score=70,
            is_guest=True,
            session_key=self.session_key,
        )

    @patch("public_checker.views.send_public_scan_report_email")
    def test_german_header_is_forwarded_to_celery_task(self, mock_task):
        url = f"/api/v1/public/scan/{self.scan.id}/email/"
        resp = self.client.post(
            url, {"email": "test-de@example.com"}, format="json",
            HTTP_ACCEPT_LANGUAGE="de-DE,de;q=0.9,en;q=0.8",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(mock_task.delay.called)
        _, kwargs = mock_task.delay.call_args
        self.assertEqual(kwargs.get("language_code"), "de")

    @patch("public_checker.views.send_public_scan_report_email")
    def test_foreign_session_cannot_email_guest_scan_report(self, mock_task):
        """Un visiteur étranger ne peut pas faire envoyer le rapport."""
        stranger = APIClient()
        stranger.session.save()

        resp = stranger.post(
            f"/api/v1/public/scan/{self.scan.id}/email/",
            {"email": "attacker@example.com"},
            format="json",
        )

        self.assertEqual(resp.status_code, 404)
        self.assertFalse(mock_task.delay.called)

    @patch("public_checker.views.send_public_scan_report_email")
    def test_unknown_scan_id_is_rejected(self, mock_task):
        resp = self.client.post(
            f"/api/v1/public/scan/{uuid.uuid4()}/email/",
            {"email": "test@example.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(mock_task.delay.called)
