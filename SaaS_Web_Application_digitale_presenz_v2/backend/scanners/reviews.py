"""Reviews scanner (placeholder)."""
import logging
from typing import Any

from .base import BaseScanner, ScanResult

logger = logging.getLogger(__name__)


class ReviewsScanner(BaseScanner):
    """Check online reviews."""
    
    name = "reviews"
    timeout = 5
    
    def scan(self, domain: str) -> ScanResult:
        """Placeholder for reviews scanning."""
        return self._create_result(
            score=0,
            status="not_configured",
            message="Reviews scanning not yet implemented",
            recommendation="Integration with Google My Business, Yelp, etc. is planned.",
            note="Future integration with Google My Business, Yelp, etc.",
        )


reviews_scanner = ReviewsScanner()
