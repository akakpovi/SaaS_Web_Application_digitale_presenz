from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from subscriptions.models import Plan, Subscription
from websites.models import Website


class PaidSuiteGateTest(TestCase):
    """SEO, reputation and advanced security runs are paid-plan actions.

    Reads stay open so a downgraded account keeps its history; launching a new
    run must answer the same structured 403 as the other quotas, which is what
    lets the frontend open the upgrade panel from the response alone.
    """

    def setUp(self) -> None:
        self.free_plan, _ = Plan.objects.get_or_create(
            tier=Plan.Tier.FREE,
            defaults={"name": "Free", "price_monthly": 0, "max_websites": 1},
        )
        self.pro_plan, _ = Plan.objects.get_or_create(
            tier=Plan.Tier.PRO,
            defaults={"name": "Pro", "price_monthly": 9, "max_websites": 10},
        )

        self.free_user = User.objects.create_user(
            email="free-gate@test.com", password="pass1234"
        )
        self.pro_user = User.objects.create_user(
            email="pro-gate@test.com", password="pass1234"
        )
        Subscription.objects.filter(user=self.pro_user).update(plan=self.pro_plan)

        self.free_site = Website.objects.create(
            owner=self.free_user, domain="free-gate.example"
        )
        self.pro_site = Website.objects.create(
            owner=self.pro_user, domain="pro-gate.example"
        )
        self.client = APIClient()

    def _assert_paid_plan_required(self, response) -> None:
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "paid_plan_required")
        self.assertEqual(response.data["required_plan"], "pro")
        self.assertEqual(response.data["plan"], "free")
        self.assertEqual(response.data["upgrade_url"], "/app/billing")

    def test_free_cannot_run_seo_audit(self) -> None:
        self.client.force_authenticate(self.free_user)
        response = self.client.post(
            f"/api/v1/websites/{self.free_site.id}/seo/audits/run/"
        )
        self._assert_paid_plan_required(response)

    @patch("seo.views.run_seo_audit.delay")
    def test_pro_can_run_seo_audit(self, delay) -> None:
        delay.return_value.id = "task-seo"
        self.client.force_authenticate(self.pro_user)
        response = self.client.post(
            f"/api/v1/websites/{self.pro_site.id}/seo/audits/run/"
        )
        self.assertEqual(response.status_code, 202)
        self.assertTrue(delay.called)

    def test_free_cannot_sync_reputation(self) -> None:
        self.client.force_authenticate(self.free_user)
        response = self.client.post(
            f"/api/v1/websites/{self.free_site.id}/social/sync/"
        )
        self._assert_paid_plan_required(response)

    @patch("social.views.track_brand_mentions.delay")
    @patch("social.views.sync_social_profiles.delay")
    def test_pro_can_sync_reputation(self, sync, mentions) -> None:
        self.client.force_authenticate(self.pro_user)
        response = self.client.post(f"/api/v1/websites/{self.pro_site.id}/social/sync/")
        self.assertEqual(response.status_code, 202)
        self.assertTrue(sync.called)
        self.assertTrue(mentions.called)

    def test_free_cannot_run_security_scan(self) -> None:
        self.client.force_authenticate(self.free_user)
        response = self.client.post(
            f"/api/v1/websites/{self.free_site.id}/security/scan/"
        )
        self._assert_paid_plan_required(response)

    @patch("advanced_security.views.run_security_scan.delay")
    def test_pro_can_run_security_scan(self, delay) -> None:
        delay.return_value.id = "task-security"
        self.client.force_authenticate(self.pro_user)
        response = self.client.post(
            f"/api/v1/websites/{self.pro_site.id}/security/scan/"
        )
        self.assertEqual(response.status_code, 202)
        self.assertTrue(delay.called)

    def test_free_can_still_read_incidents(self) -> None:
        self.client.force_authenticate(self.free_user)
        response = self.client.get(
            f"/api/v1/websites/{self.free_site.id}/security/incidents/"
        )
        self.assertEqual(response.status_code, 200)
