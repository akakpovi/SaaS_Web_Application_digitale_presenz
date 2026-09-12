"""API tests for the asynchronous public website checker."""

import uuid
from unittest.mock import patch

from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase


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

        self.assertEqual(
            response.status_code,
            status.HTTP_202_ACCEPTED,
        )

        self.assertIn("id", response.data)
        self.assertIn("scan_id", response.data)
        self.assertIn("poll_url", response.data)

        self.assertEqual(
            response.data["id"],
            response.data["scan_id"],
        )
        self.assertEqual(
            response.data["domain"],
            "example.com",
        )
        self.assertEqual(
            response.data["status"],
            "queued",
        )
        self.assertEqual(
            response.data["progress"],
            0,
        )
        self.assertIsNone(
            response.data["health_score"],
        )
        self.assertIsNone(
            response.data["health_status"],
        )
        self.assertEqual(
            response.data["checks"],
            [],
        )

        scan_id = response.data["scan_id"]

        self.assertEqual(
            response.data["poll_url"],
            f"/api/v1/public/check/{scan_id}/",
        )

        cached_state = cache.get(
            f"public_scan:{scan_id}"
        )

        self.assertIsNotNone(cached_state)
        self.assertEqual(
            cached_state["scan_id"],
            scan_id,
        )
        self.assertEqual(
            cached_state["domain"],
            "example.com",
        )
        self.assertEqual(
            cached_state["status"],
            "queued",
        )

        mock_delay.assert_called_once_with(
            "example.com",
            scan_id,
        )

    def test_create_public_scan_invalid_domain(self) -> None:
        response = self.client.post(
            "/api/v1/public/check/",
            {"domain": "http://example.com"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_create_public_scan_blocks_raw_private_ip(self) -> None:
        response = self.client.post(
            "/api/v1/public/check/",
            {"domain": "127.0.0.1"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_poll_public_scan_processing(self) -> None:
        scan_id = str(uuid.uuid4())

        cache.set(
            f"public_scan:{scan_id}",
            {
                "id": scan_id,
                "scan_id": scan_id,
                "domain": "example.com",
                "status": "processing",
                "progress": 0,
                "health_score": None,
                "health_status": None,
                "checks": [],
            },
            timeout=900,
        )

        response = self.client.get(
            f"/api/v1/public/check/{scan_id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["scan_id"],
            scan_id,
        )
        self.assertEqual(
            response.data["status"],
            "processing",
        )
        self.assertEqual(
            response.data["progress"],
            0,
        )
        self.assertIsNone(
            response.data["health_score"],
        )

    def test_poll_public_scan_completed(self) -> None:
        scan_id = str(uuid.uuid4())

        cache.set(
            f"public_scan:{scan_id}",
            {
                "id": scan_id,
                "scan_id": scan_id,
                "domain": "example.com",
                "status": "completed",
                "progress": 100,
                "health_score": 85,
                "health_status": "healthy",
                "scanned_at": "2026-08-25T10:00:00Z",
                "checks": [
                    {
                        "category": "website",
                        "status": "healthy",
                        "score": 20,
                        "message": "OK",
                        "details": {},
                        "recommendation": "",
                    }
                ],
            },
            timeout=900,
        )

        response = self.client.get(
            f"/api/v1/public/check/{scan_id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["scan_id"],
            scan_id,
        )
        self.assertEqual(
            response.data["status"],
            "completed",
        )
        self.assertEqual(
            response.data["progress"],
            100,
        )
        self.assertEqual(
            response.data["health_score"],
            85,
        )
        self.assertEqual(
            response.data["health_status"],
            "healthy",
        )
        self.assertEqual(
            len(response.data["checks"]),
            1,
        )

    def test_poll_unknown_public_scan_returns_404(self) -> None:
        scan_id = str(uuid.uuid4())

        response = self.client.get(
            f"/api/v1/public/check/{scan_id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
    @patch("public_checker.views.run_public_scan.delay")
    def test_public_scan_rate_limit(
        self,
        mock_delay,
    ) -> None:
        for index in range(10):
            response = self.client.post(
                "/api/v1/public/check/",
                {
                    "domain": f"site{index}.example.com",
                },
                format="json",
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_202_ACCEPTED,
            )

        response = self.client.post(
            "/api/v1/public/check/",
            {
                "domain": "site10.example.com",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

        self.assertEqual(
            mock_delay.call_count,
            10,
        )