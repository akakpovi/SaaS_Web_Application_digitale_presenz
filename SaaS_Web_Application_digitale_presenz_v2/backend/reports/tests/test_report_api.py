from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from reports.models import Report
from scans.models import CheckResult, Scan
from websites.models import Website


class ReportApiTest(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user("report-api@example.com", "CorrectHorse1!")
        self.other = User.objects.create_user(
            "report-api2@example.com", "CorrectHorse2!"
        )
        self.website = Website.objects.create(owner=self.user, domain="reports.example")
        self.scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.COMPLETED,
            health_score=85,
            health_status="healthy",
        )
        CheckResult.objects.create(
            scan=self.scan,
            category=CheckResult.Category.SSL,
            status="healthy",
            score=20,
            summary="Certificate valid",
            recommendation="Renew before expiry.",
        )
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}"
        )

    def test_requires_authentication(self) -> None:
        response = APIClient().get("/api/v1/reports/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_materialises_report_from_real_scans(self) -> None:
        response = self.client.get("/api/v1/reports/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["website_domain"], "reports.example")
        self.assertEqual(row["current_score"], 85)
        self.assertEqual(row["total_scans"], 1)
        self.assertEqual(row["latest_scan_id"], self.scan.id)
        self.assertEqual(row["check_breakdown"]["ssl"]["max_score"], 20)
        self.assertEqual(row["check_breakdown"]["ssl"]["avg_score"], 20.0)
        self.assertTrue(Report.objects.filter(user=self.user).exists())

    def test_list_is_idempotent(self) -> None:
        self.client.get("/api/v1/reports/")
        before = Report.objects.filter(user=self.user).count()
        self.client.get("/api/v1/reports/")
        self.assertEqual(Report.objects.filter(user=self.user).count(), before)

    def test_empty_account_returns_no_report(self) -> None:
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.other)}"
        )
        response = client.get("/api/v1/reports/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"results": [], "count": 0})

    def test_other_users_reports_are_not_listed(self) -> None:
        self.client.get("/api/v1/reports/")
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.other)}"
        )
        response = client.get("/api/v1/reports/")
        self.assertEqual(response.data["count"], 0)
