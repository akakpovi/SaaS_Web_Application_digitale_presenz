from datetime import date

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from reports.models import Report
from reports.services import generate_report_data
from scans.models import CheckResult, Scan
from websites.models import Website


class ReportModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="rep@test.com", password="pass1234")
        self.website = Website.objects.create(owner=self.user, domain="report.com")

    def test_create_report(self):
        report = Report.objects.create(
            user=self.user,
            website=self.website,
            period=Report.Period.MONTHLY,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
        )
        self.assertEqual(report.status, Report.Status.PENDING)
        self.assertIsNone(report.current_score)

    def test_score_trend_up(self):
        report = Report(current_score=80, previous_score=70, score_change=10)
        self.assertEqual(report.score_trend, "up")

    def test_score_trend_down(self):
        report = Report(current_score=60, previous_score=70, score_change=-10)
        self.assertEqual(report.score_trend, "down")

    def test_score_trend_stable(self):
        report = Report(current_score=70, previous_score=70, score_change=0)
        self.assertEqual(report.score_trend, "stable")

    def test_score_trend_neutral(self):
        report = Report(score_change=None)
        self.assertEqual(report.score_trend, "neutral")

    def test_unique_constraint(self):
        from django.db import IntegrityError

        Report.objects.create(
            user=self.user,
            website=self.website,
            period=Report.Period.MONTHLY,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
        )
        with self.assertRaises(IntegrityError):
            Report.objects.create(
                user=self.user,
                website=self.website,
                period=Report.Period.MONTHLY,
                period_start=date(2024, 1, 1),
                period_end=date(2024, 1, 31),
            )


class GenerateReportDataTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="rep2@test.com", password="pass1234")
        self.website = Website.objects.create(owner=self.user, domain="report2.com")

    def test_no_scans_returns_empty(self):
        data = generate_report_data(self.website, date(2024, 1, 1), date(2024, 1, 31))
        self.assertEqual(data["total_scans"], 0)
        self.assertIsNone(data["current_score"])

    def test_with_scans(self):
        scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.COMPLETED,
            health_score=75,
            health_status="healthy",
        )
        CheckResult.objects.create(
            scan=scan,
            category="ssl",
            status="healthy",
            score=20,
            summary="SSL OK",
        )
        today = date.today()
        data = generate_report_data(self.website, today, today)
        self.assertEqual(data["total_scans"], 1)
        self.assertEqual(data["current_score"], 75)
