from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass
class ReviewData:
    external_id: str
    author_name: str
    rating: Decimal | None
    text: str
    review_date: datetime | None
    author_photo: str = ""
    language: str = ""
    raw_data: dict = field(default_factory=dict)


class ReviewProvider(ABC):
    """Base class for review platform integrations."""

    def __init__(self, config: dict) -> None:
        self.config = config

    @abstractmethod
    def fetch_reviews(self, limit: int = 50) -> list[ReviewData]:
        """Fetch reviews from the platform. Returns list of ReviewData."""
        ...

    @abstractmethod
    def validate_config(self) -> list[str]:
        """Return list of validation errors. Empty = valid."""
        ...

    def get_average_rating(self, reviews: list[ReviewData]) -> Decimal | None:
        ratings = [r.rating for r in reviews if r.rating is not None]
        if not ratings:
            return None
        return Decimal(str(round(sum(float(r) for r in ratings) / len(ratings), 2)))
