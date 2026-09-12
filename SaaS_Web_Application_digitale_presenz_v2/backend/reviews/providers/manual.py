from .base import ReviewData, ReviewProvider


class ManualReviewProvider(ReviewProvider):
    """Provider for manually-entered reviews (no external API)."""

    def fetch_reviews(self, limit: int = 50) -> list[ReviewData]:
        # Manual reviews are entered directly via API, no fetch needed
        return []

    def validate_config(self) -> list[str]:
        return []
