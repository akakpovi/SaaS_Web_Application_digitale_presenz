import logging
from django.utils import timezone
from core.security import safe_request
from reviews.models import Review, ReviewSource

logger = logging.getLogger(__name__)

class ReviewSyncService:
    def __init__(self, source: ReviewSource) -> None:
        self.source = source

    def sync(self) -> dict:
        provider = self.source.provider
        config = self.source.config or {}
        new_ids = []

        if provider == ReviewSource.Provider.GOOGLE:
            place_id = config.get("place_id")
            api_key = config.get("api_key")
            if place_id and api_key:
                url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=reviews&key={api_key}"
                try:
                    resp = safe_request("GET", url, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json().get("result", {})
                        for r in data.get("reviews", []):
                            ext_id = str(r.get("author_name", "")) + "_" + str(r.get("time", ""))
                            review_date = timezone.datetime.fromtimestamp(r.get("time", 0), tz=timezone.utc)
                            _, created = Review.objects.get_or_create(
                                source=self.source,
                                external_id=ext_id,
                                defaults={
                                    "author_name": r.get("author_name", "Anonymous"),
                                    "rating": float(r.get("rating", 5)),
                                    "text": r.get("text", ""),
                                    "language": r.get("language", "fr"),
                                    "review_date": review_date,
                                    "raw_data": r
                                }
                            )
                            if created:
                                new_ids.append(ext_id)
                except Exception as exc:
                    logger.error("GMB sync error: %s", exc)
        
        self.source.last_synced_at = timezone.now()
        self.source.save(update_fields=["last_synced_at"])
        return {"status": "ok", "new_count": len(new_ids), "ids": new_ids}
