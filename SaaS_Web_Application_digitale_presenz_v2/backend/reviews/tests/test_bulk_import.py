import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from accounts.models import User
from reviews.models import Review, ReviewImportJob, ReviewSentiment, ReviewSource
from reviews.services.bulk_import import BulkImporter
from websites.models import Website

MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class BulkImporterTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="import@test.com", password="pass1234"
        )
        self.website = Website.objects.create(owner=self.user, domain="import.com")
        self.source = ReviewSource.objects.create(
            user=self.user,
            website=self.website,
            provider=ReviewSource.Provider.MANUAL,
            name="CSV import",
        )

    def _job(self, content: str, file_type: str = "csv") -> ReviewImportJob:
        upload = SimpleUploadedFile(
            f"reviews.{file_type}",
            content.encode("utf-8"),
            content_type="text/csv" if file_type == "csv" else "application/json",
        )
        return ReviewImportJob.objects.create(
            user=self.user,
            source=self.source,
            file=upload,
            file_type=file_type,
        )

    def _run(self, content: str, file_type: str = "csv") -> ReviewImportJob:
        job = self._job(content, file_type)
        BulkImporter(job).process()
        job.refresh_from_db()
        return job

    def test_csv_rows_are_imported_with_a_sentiment(self):
        job = self._run(
            "author,rating,text,review_date,external_id\n"
            'Ada,5,"Excellent service",2026-10-01T10:00:00+00:00,a1\n'
            'Bob,2,"Slow response",2026-10-02T09:00:00+00:00,b1\n'
        )

        self.assertEqual(job.status, ReviewImportJob.Status.COMPLETED)
        self.assertEqual(job.total_rows, 2)
        self.assertEqual(job.imported_count, 2)
        self.assertEqual(job.failed_count, 0)

        ada = Review.objects.get(external_id="a1")
        bob = Review.objects.get(external_id="b1")

        # The review list shows the sentiment badge: an import must not leave
        # every row neutral.
        self.assertEqual(ada.sentiment, Review.Sentiment.POSITIVE)
        self.assertEqual(bob.sentiment, Review.Sentiment.NEGATIVE)

        details = ReviewSentiment.objects.get(review=ada)
        self.assertGreater(details.confidence, 0.5)
        self.assertTrue(details.keywords)

    def test_reimport_updates_instead_of_failing_on_external_id(self):
        csv = "author,rating,text,external_id\nAda,4,Good service,a1\n"
        self._run(csv)

        job = self._run("author,rating,text,external_id\nAda,5,Excellent service,a1\n")

        self.assertEqual(job.failed_count, 0)
        self.assertEqual(Review.objects.filter(external_id="a1").count(), 1)
        ada = Review.objects.get(external_id="a1")
        self.assertEqual(ada.rating, 5)
        self.assertEqual(ada.sentiment, Review.Sentiment.POSITIVE)

    def test_blank_rating_defaults_and_missing_author_is_reported(self):
        job = self._run(
            "author,rating,text\nAda,,Excellent service\n,5,No author here\n"
        )

        self.assertEqual(job.imported_count, 1)
        self.assertEqual(job.failed_count, 1)
        self.assertTrue(job.errors[0].startswith("Row 2:"))
        self.assertEqual(Review.objects.get(author_name="Ada").rating, 5)

    def test_json_payload_is_accepted(self):
        job = self._run(
            '[{"name": "Ada", "rating": 5, "content": "Great, thanks!"}]',
            file_type="json",
        )

        self.assertEqual(job.imported_count, 1)
        self.assertEqual(Review.objects.count(), 1)
