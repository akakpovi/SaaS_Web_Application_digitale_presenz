"""The overview endpoint must expose only stored measurements."""

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from scans.models import CheckResult, Scan
from websites.models import Website


class MonitoringOverviewApiTest(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user("monitor@example.com", "CorrectHorse1!")
        self.other = User.objects.create_user("other@example.com", "CorrectHorse2!")
        self.website = Website.objects.create(owner=self.user, domain="monitor.example")
        self.other_website = Website.objects.create(
            owner=self.other, domain="other.example"
        )

        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}"
        )

    def _completed_scan(self, website: Website, current_status: str, score: int = 80):
        scan = Scan.objects.create(
            website=website,
            status=Scan.Status.COMPLETED,
            health_score=score,
            health_status="healthy",
        )
        CheckResult.objects.create(
            scan=scan,
            category=CheckResult.Category.UPTIME,
            status="healthy" if current_status == "up" else "critical",
            score=None,
            summary="Uptime probe",
            technical_details={"current_status": current_status},
        )
        return scan

    def test_requires_authentication(self) -> None:
        response = APIClient().get("/api/v1/monitoring/overview/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_account_has_no_invented_values(self) -> None:
        response = self.client.get("/api/v1/monitoring/overview/?period=30D")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["summary"]["uptime_percent"])
        self.assertEqual(response.data["summary"]["uptime_checks"], 0)
        self.assertEqual(response.data["series"], [])
        self.assertEqual(response.data["events"], [])
        # One monitoring config exists, but no measurement was ever recorded.
        self.assertEqual(response.data["summary"]["monitored_websites"], 1)

    def test_uptime_is_computed_from_stored_checks(self) -> None:
        self._completed_scan(self.website, "up")
        self._completed_scan(self.website, "up")
        self._completed_scan(self.website, "down")

        response = self.client.get("/api/v1/monitoring/overview/?period=24H")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["summary"]["uptime_checks"], 3)
        self.assertEqual(response.data["summary"]["failed_checks"], 1)
        self.assertAlmostEqual(
            response.data["summary"]["uptime_percent"], 66.67, places=2
        )
        self.assertEqual(len(response.data["series"]), 1)
        self.assertEqual(response.data["series"][0]["checks"], 3)
        self.assertEqual(len(response.data["events"]), 3)
        self.assertEqual(response.data["events"][0]["kind"], "scan")

    def test_partial_scan_is_an_incomplete_event_not_a_success(self) -> None:
        Scan.objects.create(
            website=self.website,
            status=Scan.Status.PARTIAL,
            health_score=62,
            health_status="warning",
            failure_message="Partial scan: nuclei timeout.",
            completed_at=timezone.now(),
        )

        response = self.client.get("/api/v1/monitoring/overview/?period=24H")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = response.data["events"][0]
        self.assertEqual(event["kind"], "scan")
        self.assertEqual(event["status"], "partial")
        self.assertEqual(event["severity"], "warning")
        self.assertEqual(event["title"], "Scan incomplete")
        self.assertIn("nuclei timeout", event["detail"])

    def test_other_users_data_is_not_visible(self) -> None:
        self._completed_scan(self.other_website, "down", score=10)
        response = self.client.get("/api/v1/monitoring/overview/?period=24H")
        self.assertEqual(response.data["summary"]["uptime_checks"], 0)
        self.assertEqual(
            [w["domain"] for w in response.data["websites"]], ["monitor.example"]
        )

    def test_foreign_website_filter_is_404(self) -> None:
        response = self.client.get(
            f"/api/v1/monitoring/overview/?website_id={self.other_website.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_period_falls_back_to_24h(self) -> None:
        response = self.client.get("/api/v1/monitoring/overview/?period=42Y")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["period"], "24H")
