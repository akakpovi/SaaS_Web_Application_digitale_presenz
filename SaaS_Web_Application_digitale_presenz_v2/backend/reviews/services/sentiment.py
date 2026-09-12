import logging
import re
from dataclasses import dataclass, field
from reviews.models import Review

logger = logging.getLogger(__name__)

@dataclass
class SentimentResult:
    sentiment: str = Review.Sentiment.NEUTRAL
    confidence: float = 0.5
    emotions: dict = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)
    language: str = "fr"

class MultilingualSentimentAnalyzer:
    STOPWORDS = {
        "fr": {"le", "la", "les", "un", "une", "des", "du", "de", "et", "est", "pour", "dans", "avec", "sur", "ce", "cette", "qui", "que", "nous", "vous", "très", "tout"},
        "en": {"the", "a", "an", "and", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "with", "by", "from", "this", "that", "we", "you", "very"},
        "de": {"der", "die", "das", "ein", "eine", "einen", "und", "ist", "sind", "war", "in", "im", "auf", "zu", "für", "von", "mit", "bei", "es", "dies", "wir", "sehr"}
    }

    NEGATIONS = {
        "pas", "plus", "jamais", "aucun", "aucune", "guère", "nullement",
        "not", "never", "no", "n't", "hardly", "barely",
        "nicht", "kein", "keine", "keinen", "nie", "niemals", "keineswegs"
    }

    POSITIVE_WORDS = {
        "excellent", "parfait", "super", "génial", "recommande", "recommander", "bon", "bonne",
        "propre", "rapide", "merci", "top", "délicieux", "agréable", "formidable", "magnifique",
        "adore", "adoré", "bravo", "chaleureux", "impeccable", "satisfait", "sympa", "merveilleux",
        "aimable", "professionnel", "convivial", "qualité", "irréprochable",
        "perfect", "great", "awesome", "recommend", "good", "clean", "fast",
        "thanks", "thank", "amazing", "delicious", "wonderful", "fantastic", "love", "loved",
        "best", "friendly", "superb", "brilliant", "outstanding", "helpful", "nice", "fabulous",
        "flawless", "satisfied", "enjoyed", "top-notch", "impressed", "pleased",
        "ausgezeichnet", "perfekt", "toll", "genial", "empfehlen", "empfehlenswert",
        "guter", "gutes", "sauber", "schnell", "danke", "lecker", "wunderbar",
        "schön", "hervorragend", "begeistert", "spitze", "zufrieden",
        "klasse", "prima", "köstlich", "tadellos", "gemütlich", "herzlich", "lohnenswert"
    }

    NEGATIVE_WORDS = {
        "mauvais", "mauvaise", "horrible", "déçu", "déçue", "décevant", "nul", "nulle",
        "arnaque", "catastrophe", "catastrophique", "lent", "lente", "froid", "froide",
        "impoli", "impolie", "sale", "pire", "dégueulasse", "inacceptable", "honte", "fuyez",
        "fuir", "voleur", "médiocre", "déplorable", "cher", "chère", "dommage", "déception",
        "désagréable", "regrette", "évitez", "scandaleux", "immonde",
        "bad", "disappointed", "disappointing", "terrible", "scam", "slow",
        "rude", "dirty", "worst", "awful", "poor", "sucks", "waste", "useless",
        "disgusting", "unprofessional", "unacceptable", "avoid", "broken", "ruined", "overpriced",
        "regret", "cold", "pathetic", "annoying", "garbage", "shame",
        "schlecht", "schlechte", "schlechter", "schrecklich", "enttäuscht", "enttäuschend",
        "katastrophe", "katastrophal", "langsam", "kalt", "unfreundlich", "schmutzig", "dreckig",
        "schlimmste", "ekelhaft", "unverschämt", "abzocke", "meiden", "unhöflich", "minderwertig",
        "ärgerlich", "mies", "grauenhaft", "mangelhaft", "überteuert", "furchtbar", "schade", "unangenehm"
    }

    def detect_language(self, text: str) -> str:
        text_lower = text.lower()
        if any(c in text_lower for c in "äöüß"):
            return "de"
        if any(c in text_lower for c in "éèêàâçùîô"):
            return "fr"
        words = set(re.findall(r"[a-z0-9à-ÿ]+", text_lower))
        scores = {lang: len(words.intersection(sw)) for lang, sw in self.STOPWORDS.items()}
        detected = max(scores, key=scores.get)
        return detected if scores[detected] > 0 else "fr"

    def analyze(self, text: str, lang: str | None = None) -> SentimentResult:
        if not text or not text.strip():
            return SentimentResult()

        detected_lang = lang if lang in ["fr", "en", "de"] else self.detect_language(text)
        text_lower = text.lower()
        tokens = re.findall(r"[a-z0-9à-ÿ'-]+", text_lower)

        pos_count = 0.0
        neg_count = 0.0
        negate_next = False

        for token in tokens:
            if token in self.NEGATIONS:
                negate_next = True
                continue

            is_pos = token in self.POSITIVE_WORDS
            is_neg = token in self.NEGATIVE_WORDS

            if is_pos:
                if negate_next:
                    neg_count += 1.2
                else:
                    pos_count += 1.0
            elif is_neg:
                if negate_next:
                    pos_count += 0.8
                else:
                    neg_count += 1.0

            negate_next = False

        all_sw = self.STOPWORDS["fr"] | self.STOPWORDS["en"] | self.STOPWORDS["de"]
        keywords = [t for t in tokens if len(t) > 3 and t not in all_sw and t not in self.NEGATIONS]
        unique_keywords = list(dict.fromkeys(keywords))[:6]

        if pos_count > neg_count:
            diff = pos_count - neg_count
            confidence = min(0.60 + (diff * 0.12), 0.98)
            return SentimentResult(
                sentiment=Review.Sentiment.POSITIVE,
                confidence=round(confidence, 2),
                emotions={"joy": round(confidence, 2), "satisfaction": 0.85},
                keywords=unique_keywords,
                language=detected_lang,
            )
        elif neg_count > pos_count:
            diff = neg_count - pos_count
            confidence = min(0.60 + (diff * 0.12), 0.98)
            return SentimentResult(
                sentiment=Review.Sentiment.NEGATIVE,
                confidence=round(confidence, 2),
                emotions={"frustration": round(confidence, 2), "dissatisfaction": 0.85},
                keywords=unique_keywords,
                language=detected_lang,
            )

        return SentimentResult(
            sentiment=Review.Sentiment.NEUTRAL,
            confidence=0.50,
            emotions={"neutral": 1.0},
            keywords=unique_keywords,
            language=detected_lang,
        )

def get_analyzer():
    return MultilingualSentimentAnalyzer()
