from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_review_sentiment(self, review_id: str) -> dict:
    from reviews.models import Review, ReviewSentiment
    from reviews.services.sentiment import get_analyzer
    try:
        review = Review.objects.get(id=review_id)
        if not review.text.strip():
            return {"status": "empty"}
        res = get_analyzer().analyze(review.text, review.language or "fr")
        review.sentiment = res.sentiment
        review.language = res.language
        review.save(update_fields=["sentiment", "language"])
        
        ReviewSentiment.objects.update_or_create(
            review=review,
            defaults={
                "confidence": res.confidence,
                "emotions": res.emotions,
                "keywords": res.keywords,
                "language_detected": res.language
            }
        )
        return {"status": "completed", "sentiment": res.sentiment}
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task
def sync_review_source(source_id: int) -> dict:
    from reviews.models import ReviewSource
    from reviews.services.sync import ReviewSyncService
    source = ReviewSource.objects.get(id=source_id)
    res = ReviewSyncService(source).sync()
    for ext_id in res.get("ids", []):
        try:
            from reviews.models import Review
            rev = Review.objects.get(source=source, external_id=ext_id)
            analyze_review_sentiment.delay(str(rev.id))
        except Review.DoesNotExist:
            pass
    return res

@shared_task
def sync_all_review_sources() -> None:
    from reviews.models import ReviewSource
    for source in ReviewSource.objects.filter(enabled=True).exclude(provider="manual"):
        sync_review_source.delay(source.id)

@shared_task
def process_review_import(job_id: str) -> dict:
    from reviews.models import ReviewImportJob
    from reviews.services.bulk_import import BulkImporter
    job = ReviewImportJob.objects.get(id=job_id)
    return BulkImporter(job).process()
