import csv
import io
import json
import logging
from django.utils import timezone
from reviews.models import Review, ReviewImportJob

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
                    self.job.errors.append(f"Row {i+1}: {exc}")
                if (i + 1) % 50 == 0:
                    self.job.save(update_fields=["imported_count", "failed_count", "errors"])

            self.job.status = ReviewImportJob.Status.COMPLETED
            self.job.completed_at = timezone.now()
        except Exception as exc:
            logger.exception("Bulk import error")
            self.job.status = ReviewImportJob.Status.FAILED
            self.job.errors.append(str(exc))
        finally:
            self.job.save()
        return {"total": self.job.total_rows, "imported": self.job.imported_count, "failed": self.job.failed_count}

    def _create_review(self, row: dict) -> None:
        author = row.get("author") or row.get("author_name") or row.get("name", "")
        if not author:
            raise ValueError("author_name missing")
        rating = float(row.get("rating", 5))
        text = row.get("text") or row.get("content") or ""
        ext_id = str(row.get("external_id", ""))

        review_date = timezone.now()
        raw_date = row.get("review_date") or row.get("date")
        if raw_date:
            try:
                review_date = timezone.datetime.fromisoformat(raw_date)
                if timezone.is_naive(review_date):
                    review_date = timezone.make_aware(review_date)
            except (ValueError, TypeError):
                pass

        Review.objects.create(
            source=self.job.source,
            author_name=author,
            rating=rating,
            text=text,
            external_id=ext_id,
            review_date=review_date,
            is_approved=True
        )
