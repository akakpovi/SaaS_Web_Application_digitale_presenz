"""
Test d'intégration — Rate-limiting 5/h
"""

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class PublicScanThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def tearDown(self):
        cache.clear()

    def test_five_requests_pass_sixth_is_throttled(self):
        payload = {"url": "https://example.com"}
        statuses = []
        for _ in range(6):
            resp = self.client.post(
                "/api/v1/public/scan/",
                payload,
                format="json",
                REMOTE_ADDR="10.0.0.99",
            )
            statuses.append(resp.status_code)

        print("📡 Statuts observés (6 requêtes) :", statuses)
        self.assertNotIn(
            429, statuses[:5], "Les 5 premières requêtes ne doivent PAS être bloquées"
        )
        self.assertEqual(statuses[5], 429, "La 6e requête doit renvoyer HTTP 429")
