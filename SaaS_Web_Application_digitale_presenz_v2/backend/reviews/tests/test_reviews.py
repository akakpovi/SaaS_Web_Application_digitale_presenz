from django.test import TestCase

from accounts.models import User
from reviews.models import ResponseDraft, Review, ReviewSource
from websites.models import Website


class ReviewSourceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="rv@test.com", password="pass1234")
        self.website = Website.objects.create(owner=self.user, domain="review.com")

    def test_create_source(self):
        source = ReviewSource.objects.create(
            user=self.user,
            website=self.website,
            provider=ReviewSource.Provider.MANUAL,
            name="Manual Reviews",
        )
        self.assertEqual(source.provider, "manual")
        self.assertTrue(source.enabled)

    def test_str(self):
        source = ReviewSource.objects.create(
            user=self.user,
            website=self.website,
            provider=ReviewSource.Provider.GOOGLE,
            name="Google Reviews",
        )
        self.assertIn("google", str(source))


class ReviewModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="rv2@test.com", password="pass1234")
        self.website = Website.objects.create(owner=self.user, domain="review2.com")
        self.source = ReviewSource.objects.create(
            user=self.user,
            website=self.website,
            provider=ReviewSource.Provider.MANUAL,
            name="Test Source",
        )

    def test_create_review(self):
        review = Review.objects.create(
            source=self.source,
            author_name="John Doe",
            rating="4.5",
            text="Great service!",
            sentiment=Review.Sentiment.POSITIVE,
        )
        self.assertFalse(review.is_approved)
        self.assertEqual(review.sentiment, "positive")

    def test_approve_review(self):
        review = Review.objects.create(
            source=self.source,
            author_name="Jane",
            rating="5.0",
            text="Excellent!",
        )
        self.assertFalse(review.is_approved)
        review.is_approved = True
        review.save()
        self.assertTrue(Review.objects.get(pk=review.pk).is_approved)


class ResponseDraftTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="rv3@test.com", password="pass1234")
        self.website = Website.objects.create(owner=self.user, domain="review3.com")
        self.source = ReviewSource.objects.create(
            user=self.user,
            website=self.website,
            provider=ReviewSource.Provider.MANUAL,
            name="Source",
        )
        self.review = Review.objects.create(
            source=self.source, author_name="Bob", rating="3.0", text="OK"
        )

    def test_create_draft(self):
        draft = ResponseDraft.objects.create(
            review=self.review,
            user=self.user,
            content="Thank you for your feedback!",
        )
        self.assertEqual(draft.status, ResponseDraft.Status.DRAFT)
        self.assertIsNone(draft.sent_at)
