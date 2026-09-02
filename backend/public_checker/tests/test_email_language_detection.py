"""
Test d'intégration — Détection Accept-Language
"""
from unittest.mock import patch
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from websites.models import Website
from scans.models import Scan


class PublicScanEmailLanguageDetectionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.website = Website.objects.create(domain="lang-detect.com", is_guest=True)
        self.scan = Scan.objects.create(
            website=self.website, status="completed", health_score=70, is_guest=True,
        )

    @patch("public_checker.views.send_public_scan_report_email")
    def test_german_header_is_forwarded_to_celery_task(self, mock_task):
        url = f"/api/v1/public/scan/{self.scan.id}/email/"
        resp = self.client.post(
            url, {"email": "test-de@example.com"}, format="json",
            HTTP_ACCEPT_LANGUAGE="de-DE,de;q=0.9,en;q=0.8",
        )
        print("📡 Statut réponse:", resp.status_code)
        self.assertTrue(mock_task.delay.called)
        _, kwargs = mock_task.delay.call_args
        print("🌍 language_code transmis à Celery:", kwargs.get("language_code"))
        self.assertEqual(kwargs.get("language_code"), "de")
