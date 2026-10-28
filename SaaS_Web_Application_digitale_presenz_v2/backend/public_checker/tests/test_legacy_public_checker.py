"""API tests for the asynchronous public website checker.

Ces tests décrivent le contrat réellement exposé par ``public_checker.views`` :

* ``POST /api/v1/public/check/`` crée un ``Scan`` en base et renvoie un
  identifiant **numérique** ; l'URL de polling est
  ``/api/v1/public/scan/<id>/status/``.
* ``GET /api/v1/public/scan/<id>/status/`` renvoie 200 pour un scan invité
  (public par conception) et 404 pour un scan privé lu par quelqu'un d'autre
  que son propriétaire (correctif P0-04).

Les tests historiques qui affirmaient un polling par clé de cache arbitraire
(``/api/v1/public/check/<uuid>/``) et un ``run_public_scan.delay`` prenant un
domaine décrivaient une API qui n'existe plus / n'a jamais existé et ont été
remplacés par les assertions ci-dessous.
"""

import uuid
from unittest.mock import patch

from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from scans.models import Scan


class PublicCheckerAPITests(APITestCase):
    def setUp(self) -> None:
        cache.clear()

    def tearDown(self) -> None:
        cache.clear()

    @patch("public_checker.views.run_public_scan.delay")
    def test_create_public_scan(self, mock_delay) -> None:
        response = self.client.post(
            "/api/v1/public/check/",
            {"domain": "example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        self.assertIn("id", response.data)
        self.assertIn("scan_id", response.data)
        self.assertIn("poll_url", response.data)

        self.assertEqual(response.data["id"], response.data["scan_id"])
        self.assertEqual(response.data["domain"], "example.com")
        self.assertEqual(response.data["status"], "queued")
        self.assertEqual(response.data["progress"], 0)
        self.assertIsNone(response.data["health_score"])
        self.assertEqual(response.data["health_status"], "neutral")
        self.assertEqual(response.data["checks"], [])

        # The scan is persisted with a numeric id and the polling URL points
        # at the status endpoint of that scan.
        scan_id = response.data["scan_id"]
        self.assertTrue(str(scan_id).isdigit())
        self.assertEqual(
            response.data["poll_url"],
            f"/api/v1/public/scan/{scan_id}/status/",
        )

        scan = Scan.objects.get(pk=int(scan_id))
        self.assertEqual(scan.status, Scan.Status.QUEUED)
        self.assertTrue(scan.is_guest)
        self.assertEqual(scan.trigger, Scan.Trigger.PUBLIC)
        self.assertTrue(scan.session_key)

        cached_state = cache.get(f"public_scan:{scan_id}")
        self.assertIsNotNone(cached_state)
        self.assertEqual(cached_state["scan_id"], scan_id)
        self.assertEqual(cached_state["domain"], "example.com")
        self.assertEqual(cached_state["status"], "queued")

        # The Celery task receives the database identifier of the scan.
        mock_delay.assert_called_once_with(scan.id)

    def test_create_public_scan_invalid_domain(self) -> None:
        response = self.client.post(
            "/api/v1/public/check/",
            {"domain": "http://example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_public_scan_blocks_raw_private_ip(self) -> None:
        response = self.client.post(
            "/api/v1/public/check/",
            {"domain": "127.0.0.1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("public_checker.views.run_public_scan.delay")
    def test_poll_public_scan_processing(self, mock_delay) -> None:
        """A freshly queued guest scan is pollable by its creator."""
        created = self.client.post(
            "/api/v1/public/check/",
            {"domain": "poll-me.example.com"},
            format="json",
        )
        scan_id = created.data["scan_id"]

        response = self.client.get(f"/api/v1/public/check/{scan_id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["scan_id"], scan_id)
        self.assertEqual(response.data["status"], "queued")
        # Le sérialiseur public expose 0 (et non null) tant qu'aucun score
        # n'a été calculé : le frontend ne doit jamais recevoir de score nul.
        self.assertEqual(response.data["score"], 0)
        self.assertEqual(response.data["steps"], created.data["steps"])

    @patch("public_checker.views.run_public_scan.delay")
    def test_poll_public_scan_completed(self, mock_delay) -> None:
        """A completed guest scan exposes its score, summary and checks."""
        from scans.models import CheckResult

        created = self.client.post(
            "/api/v1/public/check/",
            {"domain": "completed.example.com"},
            format="json",
        )
        scan = Scan.objects.get(pk=int(created.data["scan_id"]))
        scan.transition_to(Scan.Status.RUNNING)
        CheckResult.objects.create(
            scan=scan,
            category=CheckResult.Category.WEBSITE,
            status="healthy",
            score=20,
            summary="OK",
        )
        scan.health_score = 85
        scan.health_status = "healthy"
        scan.progress = 100
        scan.save(update_fields=["health_score", "health_status", "progress"])
        scan.transition_to(Scan.Status.COMPLETED)

        response = self.client.get(f"/api/v1/public/check/{scan.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["scan_id"], str(scan.id))
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["score"], 85)
        self.assertEqual(response.data["summary"]["passed"], 1)
        self.assertIn("website", response.data["checks"])
        self.assertEqual(response.data["checks"]["website"]["score"], 20)
        self.assertEqual(response.data["progress"], 100)

    def test_poll_unknown_public_scan_returns_404(self) -> None:
        response = self.client.get(f"/api/v1/public/check/{uuid.uuid4()}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_poll_unknown_numeric_scan_returns_404(self) -> None:
        response = self.client.get("/api/v1/public/check/999999999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_cannot_read_private_scan(self) -> None:
        """P0-04 — un scan privé ne doit jamais être lisible en anonyme."""
        from django.contrib.auth import get_user_model

        from websites.models import Website

        owner = get_user_model().objects.create_user(
            email="owner-p04@example.com", password="Str0ngPass!2026"
        )
        website = Website.objects.create(
            owner=owner, domain="private-p04.example.com", is_guest=False
        )
        scan = Scan.objects.create(
            website=website,
            status=Scan.Status.COMPLETED,
            trigger=Scan.Trigger.MANUAL,
            scan_type=Scan.ScanType.HEALTH,
            health_score=77,
            is_guest=False,
        )

        response = self.client.get(f"/api/v1/public/scan/{scan.id}/status/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("public_checker.views.run_public_scan.delay")
    def test_public_scan_rate_limit(self, mock_delay) -> None:
        for index in range(10):
            response = self.client.post(
                "/api/v1/public/check/",
                {"domain": f"site{index}.example.com"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        response = self.client.post(
            "/api/v1/public/check/",
            {"domain": "site10.example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(mock_delay.call_count, 10)
