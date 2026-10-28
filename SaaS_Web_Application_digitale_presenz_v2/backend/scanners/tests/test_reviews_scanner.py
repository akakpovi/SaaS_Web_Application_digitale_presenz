from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from scanners.reviews import ReviewsScanner


class ReviewsScannerTest(SimpleTestCase):
    def _response(self, html: str):
        return SimpleNamespace(
            body=html.encode("utf-8"),
            url="https://example.com/",
            status_code=200,
        )

    @patch("scanners.reviews.safe_request")
    def test_computes_score_from_published_rating(self, mock_request):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"LocalBusiness",
         "aggregateRating":{"@type":"AggregateRating",
         "ratingValue":"4.5","reviewCount":"128","bestRating":"5"}}
        </script>
        </head></html>
        """
        mock_request.return_value = self._response(html)

        result = ReviewsScanner().scan("example.com")

        self.assertEqual(result.score, 18)
        self.assertEqual(result.status, "healthy")
        self.assertEqual(result.details["rating"], 4.5)
        self.assertEqual(result.details["review_count"], 128)

    @patch("scanners.reviews.safe_request")
    def test_missing_markup_is_neutral_not_a_fake_score(self, mock_request):
        mock_request.return_value = self._response("<html><body>Hello</body></html>")

        result = ReviewsScanner().scan("example.com")

        self.assertIsNone(result.score)
        self.assertEqual(result.status, "neutral")
        self.assertIn("No AggregateRating", result.message)

    @patch("scanners.reviews.safe_request")
    def test_network_failure_is_an_error(self, mock_request):
        mock_request.side_effect = RuntimeError("connection refused")

        result = ReviewsScanner().scan("example.com")

        self.assertIsNone(result.score)
        self.assertEqual(result.status, "error")
