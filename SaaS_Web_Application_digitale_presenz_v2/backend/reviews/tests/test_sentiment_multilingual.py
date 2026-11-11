from django.test import TestCase
from reviews.services.sentiment import get_analyzer
from reviews.models import Review


class MultilingualSentimentTest(TestCase):
    def setUp(self):
        self.analyzer = get_analyzer()

    def test_french_sentiment(self):
        # Positif FR
        res_pos = self.analyzer.analyze(
            "Le repas était absolument délicieux et le service très rapide. Je recommande !"
        )
        self.assertEqual(res_pos.sentiment, Review.Sentiment.POSITIVE)
        self.assertEqual(res_pos.language, "fr")

        # Négatif FR avec négation
        res_neg = self.analyzer.analyze(
            "Ce restaurant n'est pas bon du tout, service lent et froid."
        )
        self.assertEqual(res_neg.sentiment, Review.Sentiment.NEGATIVE)

    def test_english_sentiment(self):
        # Positif EN
        res_pos = self.analyzer.analyze(
            "Great atmosphere, clean rooms and awesome staff. Loved it!"
        )
        self.assertEqual(res_pos.sentiment, Review.Sentiment.POSITIVE)
        self.assertEqual(res_pos.language, "en")

        # Négatif EN
        res_neg = self.analyzer.analyze(
            "Terrible experience. The place is dirty and the waiter was extremely rude."
        )
        self.assertEqual(res_neg.sentiment, Review.Sentiment.NEGATIVE)
        self.assertEqual(res_neg.language, "en")

    def test_german_sentiment(self):
        # Positif DE
        res_pos = self.analyzer.analyze(
            "Ausgezeichnetes Essen und sehr freundliche Bedienung. Absolut empfehlenswert!"
        )
        self.assertEqual(res_pos.sentiment, Review.Sentiment.POSITIVE)
        self.assertEqual(res_pos.language, "de")

        # Négatif DE
        res_neg = self.analyzer.analyze(
            "Schrecklicher Service, das Essen war kalt und ungenießbar. Nie wieder!"
        )
        self.assertEqual(res_neg.sentiment, Review.Sentiment.NEGATIVE)
        self.assertEqual(res_neg.language, "de")
