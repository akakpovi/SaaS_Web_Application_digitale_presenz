import re
import json
import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from django.utils import timezone

from core.security import safe_request
from reviews.models import ReviewSource, Review

logger = logging.getLogger(__name__)


class RealReviewDiscoveryService:
    def __init__(self, website):
        self.website = website
        self.domain = website.domain.lower().replace("www.", "").strip()

    def discover_all(self) -> Dict[str, Any]:
        results = {
            "trustpilot": self.discover_trustpilot(),
            "schema_org": self.discover_website_schema_reviews(),
        }
        total_found = sum(len(r.get("reviews", [])) for r in results.values())
        results["total_discovered"] = total_found
        return results

    def discover_trustpilot(self) -> Dict[str, Any]:
        candidates = [
            f"https://www.trustpilot.com/review/{self.domain}",
            f"https://fr.trustpilot.com/review/{self.domain}",
            f"https://de.trustpilot.com/review/{self.domain}",
            f"https://www.trustpilot.com/review/www.{self.domain}",
        ]

        for url in candidates:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                }
                
                resp = safe_request(url, method="GET", headers=headers)
                if not resp or resp.status_code != 200:
                    continue

                html = resp.text
                reviews = self._parse_trustpilot_html(html, url)
                
                if reviews:
                    source, _ = ReviewSource.objects.get_or_create(
                        website=self.website,
                        provider="trustpilot",
                        defaults={"url": url, "is_active": True}
                    )
                    
                    saved = 0
                    for r in reviews:
                        if self._save_real_review(
                            source=source,
                            external_id=r["id"],
                            author_name=r["author"],
                            rating=r["rating"],
                            text=r["text"],
                            date_str=r.get("date")
                        ):
                            saved += 1
                    
                    return {
                        "status": "success",
                        "url": url,
                        "reviews_found": len(reviews),
                        "reviews_saved": saved,
                        "reviews": reviews[:10],
                    }
            except Exception as e:
                logger.warning(f"Erreur Trustpilot {url}: {e}")
                continue

        return {"status": "not_found", "reviews": []}

    def _parse_trustpilot_html(self, html: str, source_url: str) -> List[Dict]:
        reviews = []
        soup = BeautifulSoup(html, "html.parser")

        # Fallback 1: JSON __NEXT_DATA__
        next_data = soup.find("script", id="__NEXT_DATA__")
        if next_data and next_data.string:
            try:
                data = json.loads(next_data.string)
                props = data.get("props", {}).get("pageProps", {})
                raw_reviews = props.get("reviews", [])
                for r in raw_reviews:
                    author = r.get("consumer", {}).get("displayName", "Client Trustpilot")
                    rating = r.get("rating", 5)
                    text = r.get("text", "") or r.get("title", "")
                    date = r.get("dates", {}).get("publishedDate")
                    if text:
                        h_id = hashlib.md5(f"tp_{author}_{text[:40]}".encode()).hexdigest()[:16]
                        reviews.append({
                            "id": f"tp_{r.get('id', h_id)}",
                            "author": author,
                            "rating": rating,
                            "text": text.strip(),
                            "date": date,
                            "source": "trustpilot",
                        })
                if reviews:
                    return reviews
            except Exception:
                pass

        # Fallback 2: JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") in ("LocalBusiness", "Organization", "Product"):
                        for r in item.get("review", []):
                            author = r.get("author", {}).get("name", "Client")
                            rating = float(r.get("reviewRating", {}).get("ratingValue", 5))
                            text = r.get("reviewBody", "")
                            date = r.get("datePublished")
                            if text:
                                h_id = hashlib.md5(f"tp_{author}_{text[:40]}".encode()).hexdigest()[:16]
                                reviews.append({
                                    "id": f"tp_ld_{h_id}",
                                    "author": author,
                                    "rating": int(rating),
                                    "text": text.strip(),
                                    "date": date,
                                    "source": "trustpilot",
                                })
            except Exception:
                pass

        if reviews:
            return reviews

        # Fallback 3: DOM Selectors
        review_cards = soup.select("article[data-service-review-card-item], div.styles_reviewCard__hcK1l, div.review-card")
        for card in review_cards:
            try:
                author_el = card.select_one("[data-consumer-name-typography], .typography_heading-xxs__s5HGa, .consumer-info__details")
                author = author_el.get_text(strip=True) if author_el else "Client Trustpilot"

                text_el = card.select_one("[data-service-review-text-typography], .typography_body-l__KUYFJ, .review-content__text")
                title_el = card.select_one("[data-review-title-typography], h2")
                
                full_text = ""
                if title_el:
                    full_text += title_el.get_text(strip=True) + " - "
                if text_el:
                    full_text += text_el.get_text(strip=True)
                
                full_text = full_text.strip()
                if not full_text:
                    continue

                rating = 5
                rating_img = card.select_one("img[src*='stars-'], [data-service-review-rating]")
                if rating_img:
                    alt = rating_img.get("alt", "") or rating_img.get("data-service-review-rating", "")
                    match = re.search(r"(\d)", str(alt))
                    if match:
                        rating = int(match.group(1))

                date_el = card.select_one("time")
                date_str = date_el.get("datetime") if date_el else None

                h_id = hashlib.md5(f"tp_{author}_{full_text[:40]}".encode()).hexdigest()[:16]
                reviews.append({
                    "id": f"tp_{h_id}",
                    "author": author,
                    "rating": rating,
                    "text": full_text,
                    "date": date_str,
                    "source": "trustpilot",
                })
            except Exception:
                continue

        return reviews

    def discover_website_schema_reviews(self) -> Dict[str, Any]:
        site_url = f"https://{self.domain}"
        reviews = []

        try:
            resp = safe_request(site_url, method="GET")
            if not resp or resp.status_code != 200:
                return {"status": "failed", "reviews": []}

            soup = BeautifulSoup(resp.text, "html.parser")
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "{}")
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        item_reviews = item.get("review", [])
                        if isinstance(item_reviews, dict):
                            item_reviews = [item_reviews]
                        for r in item_reviews:
                            if not isinstance(r, dict):
                                continue
                            author = r.get("author", {})
                            author_name = author.get("name", "Client vérifié") if isinstance(author, dict) else str(author)
                            rating_obj = r.get("reviewRating", {})
                            rating = int(float(rating_obj.get("ratingValue", 5))) if isinstance(rating_obj, dict) else 5
                            text = r.get("reviewBody", "") or r.get("description", "")
                            if text:
                                h_id = hashlib.md5(f"web_{author_name}_{text[:30]}".encode()).hexdigest()[:16]
                                reviews.append({
                                    "id": f"web_{h_id}",
                                    "author": author_name,
                                    "rating": rating,
                                    "text": text.strip(),
                                    "date": r.get("datePublished"),
                                    "source": "website_schema",
                                })
                except Exception:
                    continue

            if reviews:
                source, _ = ReviewSource.objects.get_or_create(
                    website=self.website,
                    provider="google",
                    defaults={"url": site_url, "is_active": True}
                )
                saved = 0
                for r in reviews:
                    if self._save_real_review(
                        source=source,
                        external_id=r["id"],
                        author_name=r["author"],
                        rating=r["rating"],
                        text=r["text"],
                        date_str=r.get("date")
                    ):
                        saved += 1
                
                return {
                    "status": "success",
                    "reviews_found": len(reviews),
                    "reviews_saved": saved,
                    "reviews": reviews,
                }
        except Exception as e:
            logger.warning(f"Erreur schema {site_url}: {e}")

        return {"status": "not_found", "reviews": []}

    def _save_real_review(self, source, external_id, author_name, rating, text, date_str) -> bool:
        clean_text = text.strip()
        if not clean_text:
            return False

        # Vérification doublon par texte exact sur ce site
        exists = Review.objects.filter(
            source__website=self.website,
            text__iexact=clean_text
        ).exists()

        if exists:
            return False

        stable_id = f"rev_{hashlib.md5((source.provider + clean_text.lower()).encode()).hexdigest()[:20]}"
        review_date = timezone.now()
        if date_str:
            try:
                clean_date = date_str.replace("Z", "+00:00")
                review_date = datetime.fromisoformat(clean_date)
                if timezone.is_naive(review_date):
                    review_date = timezone.make_aware(review_date)
            except Exception:
                review_date = timezone.now()

        review, created = Review.objects.get_or_create(
            source=source,
            external_id=stable_id,
            defaults={
                "author_name": author_name[:255] if author_name else "Client",
                "rating": max(1, min(5, int(rating))),
                "text": clean_text,
                "review_date": review_date,
            }
        )

        if created:
            try:
                from reviews.tasks import analyze_review_sentiment
                analyze_review_sentiment.delay(str(review.id))
            except Exception:
                pass

        return created
