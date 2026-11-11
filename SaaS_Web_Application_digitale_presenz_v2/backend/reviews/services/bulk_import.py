import csv
import io
import json
import logging
from django.utils import timezone
from reviews.models import Review, ReviewImportJob, ReviewSentiment
from reviews.services.sentiment import get_analyzer

logger = logging.getLogger(__name__)


class BulkImporter:
    def __init__(self, job: ReviewImportJob) -> None:
        self.job = job

    def process(self) -> dict:
        self.job.status = ReviewImportJob.Status.PROCESSING
        self.job.save(update_fields=["status"])
        try:
            content = self.job.file.read().decode("utf-8-sig")
            if self.job.file_type == "csv":
                rows = list(csv.DictReader(io.StringIO(content)))
            else:
                data = json.loads(content)
                rows = data if isinstance(data, list) else data.get("reviews", [])

            self.job.total_rows = len(rows)
            self.job.save(update_fields=["total_rows"])

            for i, row in enumerate(rows):
                try:
                    self._create_review(row)
                    self.job.imported_count += 1
                except Exception as exc:
                    self.job.failed_count += 1
                    self.job.errors.append(f"Row {i + 1}: {exc}")
                if (i + 1) % 50 == 0:
                    self.job.save(
                        update_fields=["imported_count", "failed_count", "errors"]
                    )

            self.job.status = ReviewImportJob.Status.COMPLETED
            self.job.completed_at = timezone.now()
        except Exception as exc:
            logger.exception("Bulk import error")
            self.job.status = ReviewImportJob.Status.FAILED
            self.job.errors.append(str(exc))
        finally:
            self.job.save()
        return {
            "total": self.job.total_rows,
            "imported": self.job.imported_count,
            "failed": self.job.failed_count,
        }

    def _create_review(self, row: dict) -> None:
        author = row.get("author") or row.get("author_name") or row.get("name", "")
        if not author:
            raise ValueError("author_name missing")

        # An empty rating cell must mean "not rated", not a failed row.
        raw_rating = str(row.get("rating") or "").strip()
        rating = float(raw_rating) if raw_rating else 5

        text = row.get("text") or row.get("content") or ""
        ext_id = str(row.get("external_id") or "").strip()

        review_date = timezone.now()
        raw_date = row.get("review_date") or row.get("date")
        if raw_date:
            try:
                review_date = timezone.datetime.fromisoformat(raw_date)
                if timezone.is_naive(review_date):
                    review_date = timezone.make_aware(review_date)
            except (ValueError, TypeError):
                pass

        fields = {
            "author_name": author,
            "rating": rating,
            "text": text,
            "review_date": review_date,
            "is_approved": True,
        }
        if ext_id:
            # Re-importing the same export must update, not crash on the
            # (source, external_id) unique constraint.
            review, _ = Review.objects.update_or_create(
                source=self.job.source, external_id=ext_id, defaults=fields
            )
        else:
            review = Review.objects.create(source=self.job.source, **fields)

        self._analyze(review)

    def _analyze(self, review: Review) -> None:
        """Attach the sentiment at import time.

        The list view shows a sentiment badge for every review, so deferring
        the analysis to Celery would leave freshly imported rows neutral until
        a worker picked them up — and the import task never queued it.
        """
        if not review.text.strip():
            return

        result = get_analyzer().analyze(review.text)
        review.sentiment = result.sentiment
        review.language = result.language
        review.save(update_fields=["sentiment", "language", "updated_at"])
        ReviewSentiment.objects.update_or_create(
            review=review,
            defaults={
                "confidence": result.confidence,
                "emotions": result.emotions,
                "keywords": result.keywords,
                "language_detected": result.language,
            },
        )
