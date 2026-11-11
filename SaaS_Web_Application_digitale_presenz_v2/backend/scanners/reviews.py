"""Scanner d'avis clients basé sur les données structurées du site.

Le placeholder précédent renvoyait toujours ``not_configured``.  Sans clé API
Google Business, la source fiable et vérifiable est le balisage
``schema.org/AggregateRating`` publié par le site lui-même : note moyenne,
nombre d'avis et présence du balisage.  C'est une vraie mesure, exploitable
pour alerter sur une chute de réputation ou l'absence de rich snippets.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from core.security import DomainValidationError, safe_request

from .base import BaseScanner, ScanResult

logger = logging.getLogger(__name__)

JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def _find_aggregate_rating(node: Any) -> dict | None:
    if isinstance(node, dict):
        rating = node.get("aggregateRating")
        if isinstance(rating, dict):
            return rating
        for value in node.values():
            found = _find_aggregate_rating(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_aggregate_rating(item)
            if found:
                return found
    return None


class ReviewsScanner(BaseScanner):
    """Measure the site's published review rating (schema.org)."""

    name = "reviews"
    timeout = 15

    def scan(self, domain: str) -> ScanResult:
        try:
            response = safe_request(
                f"https://{domain}",
                method="GET",
                connect_timeout=5.0,
                read_timeout=float(self.timeout),
            )
        except DomainValidationError as exc:
            return self._create_result(
                score=None,
                status="error",
                message=f"Invalid or non-public domain: {exc}",
                recommendation="Use a publicly reachable domain name.",
            )
        except Exception as exc:  # network, TLS, timeout
            logger.warning("Reviews scanner could not fetch %s: %s", domain, exc)
            return self._create_result(
                score=None,
                status="error",
                message="Website could not be reached for review analysis.",
                recommendation="Check that the site is online and serves HTTPS.",
            )

        html = response.body.decode("utf-8", errors="replace")

        for block in JSONLD_RE.findall(html):
            try:
                payload = json.loads(block.strip())
            except (ValueError, TypeError):
                continue
            rating = _find_aggregate_rating(payload)
            if not rating:
                continue

            try:
                value = float(str(rating.get("ratingValue", "")).replace(",", "."))
            except (TypeError, ValueError):
                continue
            best = float(rating.get("bestRating", 5) or 5)
            count = rating.get("reviewCount") or rating.get("ratingCount") or 0
            try:
                count = int(count)
            except (TypeError, ValueError):
                count = 0

            normalized = max(0.0, min(value / best if best else 0, 1.0))
            score = round(normalized * 20)
            healthy = normalized >= 0.8
            return self._create_result(
                score=score,
                status="healthy" if healthy else "warning",
                message=(
                    f"Published rating {value:g}/{best:g} from {count} review(s)."
                ),
                recommendation=(
                    ""
                    if healthy
                    else "Improve review volume and address recurring negative feedback."
                ),
                rating=value,
                best_rating=best,
                review_count=count,
                source_url=response.url,
            )

        return self._create_result(
            score=None,
            status="neutral",
            message="No AggregateRating structured data found on the homepage.",
            recommendation=(
                "Add schema.org AggregateRating markup (or connect a review "
                "provider) to make ratings machine-readable."
            ),
            source_url=response.url,
        )


reviews_scanner = ReviewsScanner()
