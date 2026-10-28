from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from reviews.models import ResponseDraft, Review, ReviewSource
from websites.models import Website


class ReviewSummaryApiTest(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user("sum@example.com", "CorrectHorse1!")
        self.other = User.objects.create_user("sum2@example.com", "CorrectHorse2!")
        self.website = Website.objects.create(owner=self.user, domain="sum.example")
        self.source = ReviewSource.objects.create(
            user=self.user,
            website=self.website,
            provider=ReviewSource.Provider.MANUAL,
            name="Direct feedback",
        )
        self.review = Review.objects.create(
            source=self.source,
            author_name="Ada Lovelace",
            rating="2.0",
            text="The onboarding took too long.",
            sentiment=Review.Sentiment.NEGATIVE,
        )
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}"
        )

    def test_summary_reflects_database(self) -> None:
        response = self.client.get("/api/v1/reviews/summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["average_rating"], 2.0)
        self.assertEqual(response.data["needs_response"], 1)
        self.assertEqual(response.data["by_platform"], {"manual": 1})
        self.assertEqual(response.data["sources"], 1)

    def test_summary_is_empty_without_reviews(self) -> None:
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.other)}"
        )
        response = client.get("/api/v1/reviews/summary/")
        self.assertEqual(response.data["total"], 0)
        self.assertIsNone(response.data["average_rating"])
        self.assertEqual(response.data["needs_response"], 0)

    def test_review_payload_exposes_draft_state(self) -> None:
        response = self.client.get("/api/v1/reviews/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data["results"] if isinstance(response.data, dict) else response.data
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["needs_response"])
        self.assertFalse(rows[0]["has_response"])
        self.assertIsNone(rows[0]["response_status"])

    def test_draft_response_is_persisted_and_idempotent(self) -> None:
        url = f"/api/v1/reviews/{self.review.id}/draft-response/"
        first = self.client.post(url, {}, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertIn("Ada", first.data["content"])
        self.assertEqual(ResponseDraft.objects.filter(review=self.review).count(), 1)

        second = self.client.post(url, {}, format="json")
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ResponseDraft.objects.filter(review=self.review).count(), 1)
        self.assertEqual(ResponseDraft.objects.get(review=self.review).status, "draft")

        listed = self.client.get("/api/v1/reviews/")
        rows = listed.data["results"] if isinstance(listed.data, dict) else listed.data
        self.assertTrue(rows[0]["has_response"])
        self.assertFalse(rows[0]["needs_response"])

    def test_draft_response_cannot_target_another_tenant(self) -> None:
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.other)}"
        )
        response = client.post(f"/api/v1/reviews/{self.review.id}/draft-response/", {})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(ResponseDraft.objects.filter(review=self.review).exists())
