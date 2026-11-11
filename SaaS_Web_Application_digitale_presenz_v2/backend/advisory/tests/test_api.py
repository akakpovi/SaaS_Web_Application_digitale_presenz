from __future__ import annotations

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from advisory.models import AIRecommendation, AIRecommendationRun
from organizations.models import Membership
from scans.models import CheckResult, Scan
from websites.models import Website


class RecommendationApiTests(APITestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            email="api-owner@example.com",
            password="pass1234!",
        )
        self.website = Website.objects.create(
            owner=self.owner,
            domain="api-advisor.example",
        )
        self.organization = self.website.organization
        self.assertIsNotNone(self.organization)

        self.viewer = User.objects.create_user(
            email="api-viewer@example.com",
            password="pass1234!",
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.viewer,
            role=Membership.Role.VIEWER,
        )
        self.analyst = User.objects.create_user(
            email="api-analyst@example.com",
            password="pass1234!",
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.analyst,
            role=Membership.Role.ANALYST,
        )

        self.outsider = User.objects.create_user(
            email="api-outsider@example.com",
            password="pass1234!",
        )
        Website.objects.create(
            owner=self.outsider,
            domain="api-other.example",
        )

        self.scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.COMPLETED,
            health_score=55,
            health_status="warning",
        )
        self.check_result = CheckResult.objects.create(
            scan=self.scan,
            category=CheckResult.Category.SSL,
            status="critical",
            score=0,
            summary="The TLS certificate is close to expiry.",
            recommendation="Renew the certificate.",
        )
        self.run = AIRecommendationRun.objects.create(
            scan=self.scan,
            input_hash="a" * 64,
            status=AIRecommendationRun.Status.SUCCEEDED,
            model_used="model-a",
            attempts=1,
            completed_at=timezone.now(),
        )
        self.recommendation = AIRecommendation.objects.create(
            run=self.run,
            check_result=self.check_result,
            title="Renew the TLS certificate",
            summary="The certificate expires soon.",
            action="Renew it before the expiry date.",
            effort=AIRecommendation.Effort.LOW,
            priority=AIRecommendation.Priority.HIGH,
            confidence=0.92,
        )
        self.list_url = "/api/v1/advisory/recommendations/"

    def _auth(self, user: User) -> None:
        self.client.force_authenticate(user=user)

    def test_owner_gets_persisted_ai_recommendations(self) -> None:
        self._auth(self.owner)

        response = self.client.get(self.list_url, {"scan_id": self.scan.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "ai")
        self.assertTrue(response.data["persisted"])
        self.assertEqual(response.data["run"]["status"], "succeeded")
        self.assertEqual(len(response.data["recommendations"]), 1)
        self.assertEqual(
            response.data["recommendations"][0]["id"],
            str(self.recommendation.id),
        )

    def test_viewer_can_read_recommendations(self) -> None:
        self._auth(self.viewer)

        response = self.client.get(self.list_url, {"scan_id": self.scan.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["recommendations"]), 1)

    def test_outsider_gets_404_for_foreign_scan(self) -> None:
        self._auth(self.outsider)

        response = self.client.get(self.list_url, {"scan_id": self.scan.pk})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_cannot_list_recommendations(self) -> None:
        response = self.client.get(self.list_url, {"scan_id": self.scan.pk})

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_missing_or_invalid_scan_id_is_400(self) -> None:
        self._auth(self.owner)

        missing = self.client.get(self.list_url)
        invalid = self.client.get(self.list_url, {"scan_id": "not-an-int"})

        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_failed_run_returns_deterministic_fallback_without_persistence(
        self,
    ) -> None:
        self.run.delete()
        AIRecommendationRun.objects.create(
            scan=self.scan,
            input_hash="b" * 64,
            status=AIRecommendationRun.Status.FAILED,
            error_code="rate_limit_exceeded",
            attempts=2,
            completed_at=timezone.now(),
        )
        self._auth(self.viewer)

        response = self.client.get(self.list_url, {"scan_id": self.scan.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["run"]["status"], "failed")
        self.assertEqual(response.data["source"], "deterministic")
        self.assertFalse(response.data["persisted"])
        self.assertGreaterEqual(len(response.data["recommendations"]), 1)
        self.assertTrue(
            all(
                item["id"] is None and item["source"] == "deterministic"
                for item in response.data["recommendations"]
            )
        )
        self.assertEqual(
            AIRecommendation.objects.filter(run__scan=self.scan).count(), 0
        )

    def test_viewer_cannot_accept_or_dismiss(self) -> None:
        self._auth(self.viewer)
        accept_url = (
            f"/api/v1/advisory/recommendations/{self.recommendation.id}/accept/"
        )
        dismiss_url = (
            f"/api/v1/advisory/recommendations/{self.recommendation.id}/dismiss/"
        )

        accept = self.client.post(accept_url)
        dismiss = self.client.post(dismiss_url)

        self.assertEqual(accept.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(dismiss.status_code, status.HTTP_403_FORBIDDEN)
        self.recommendation.refresh_from_db()
        self.assertEqual(
            self.recommendation.status,
            AIRecommendation.Status.PROPOSED,
        )

    def test_analyst_can_accept_and_dismiss(self) -> None:
        self._auth(self.analyst)
        accept_url = (
            f"/api/v1/advisory/recommendations/{self.recommendation.id}/accept/"
        )
        dismiss_url = (
            f"/api/v1/advisory/recommendations/{self.recommendation.id}/dismiss/"
        )

        accepted = self.client.post(accept_url)
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        self.assertEqual(accepted.data["status"], "accepted")
        self.assertEqual(accepted.data["accepted_by"], self.analyst.pk)
        self.recommendation.refresh_from_db()
        self.assertEqual(self.recommendation.status, AIRecommendation.Status.ACCEPTED)
        self.assertEqual(self.recommendation.accepted_by, self.analyst)
        self.assertIsNotNone(self.recommendation.accepted_at)

        dismissed = self.client.post(dismiss_url)
        self.assertEqual(dismissed.status_code, status.HTTP_200_OK)
        self.assertEqual(dismissed.data["status"], "dismissed")
        self.assertEqual(dismissed.data["dismissed_by"], self.analyst.pk)
        self.recommendation.refresh_from_db()
        self.assertEqual(
            self.recommendation.status,
            AIRecommendation.Status.DISMISSED,
        )
        self.assertIsNone(self.recommendation.accepted_by)
        self.assertIsNone(self.recommendation.accepted_at)
        self.assertIsNotNone(self.recommendation.dismissed_at)

    def test_outsider_cannot_accept_recommendation(self) -> None:
        self._auth(self.outsider)
        url = f"/api/v1/advisory/recommendations/{self.recommendation.id}/accept/"

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.recommendation.refresh_from_db()
        self.assertEqual(
            self.recommendation.status,
            AIRecommendation.Status.PROPOSED,
        )

    def test_accept_is_idempotent_and_keeps_first_timestamp(self) -> None:
        self._auth(self.owner)
        url = f"/api/v1/advisory/recommendations/{self.recommendation.id}/accept/"

        first = self.client.post(url)
        self.recommendation.refresh_from_db()
        first_timestamp = self.recommendation.accepted_at
        second = self.client.post(url)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.recommendation.refresh_from_db()
        self.assertEqual(self.recommendation.accepted_at, first_timestamp)

    def test_unknown_recommendation_is_404(self) -> None:
        self._auth(self.owner)

        response = self.client.post(
            "/api/v1/advisory/recommendations/"
            "00000000-0000-0000-0000-000000000000/accept/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_no_run_returns_empty_not_generated_payload(self) -> None:
        AIRecommendationRun.objects.filter(scan=self.scan).delete()
        self._auth(self.owner)

        response = self.client.get(self.list_url, {"scan_id": self.scan.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["run"])
        self.assertEqual(response.data["source"], "none")
        self.assertFalse(response.data["persisted"])
        self.assertEqual(response.data["recommendations"], [])
