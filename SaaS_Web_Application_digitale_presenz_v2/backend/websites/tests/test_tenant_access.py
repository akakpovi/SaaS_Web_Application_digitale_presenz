"""Phase F regression tests for organization-scoped websites and scans."""

from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from organizations.models import Membership, Organization
from scans.models import CheckResult, HealthStatus, Scan
from websites.models import Website


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class TenantAccessAPITests(APITestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user("owner@tenant.example", "Password123!")
        self.admin = User.objects.create_user("admin@tenant.example", "Password123!")
        self.analyst = User.objects.create_user("analyst@tenant.example", "Password123!")
        self.viewer = User.objects.create_user("viewer@tenant.example", "Password123!")
        self.outsider = User.objects.create_user("outsider@elsewhere.example", "Password123!")

        self.organization = Organization.objects.create(
            name="Tenant A",
            billing_owner=self.owner,
            is_personal=False,
        )
        for user, role in (
            (self.owner, Membership.Role.OWNER),
            (self.admin, Membership.Role.ADMIN),
            (self.analyst, Membership.Role.ANALYST),
            (self.viewer, Membership.Role.VIEWER),
        ):
            Membership.objects.create(
                organization=self.organization,
                user=user,
                role=role,
            )

        self.website = Website.objects.create(
            owner=self.owner,
            organization=self.organization,
            domain="tenant-a.example",
        )
        self.scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.COMPLETED,
            health_status=HealthStatus.HEALTHY,
            health_score=90,
        )
        self.check_result = CheckResult.objects.create(
            scan=self.scan,
            category=CheckResult.Category.WEBSITE,
            status=HealthStatus.HEALTHY,
            score=20,
            summary="Available",
            recommendation="",
            technical_details={"http_status": 200},
        )

        self.other_organization = Organization.objects.create(
            name="Tenant B",
            billing_owner=self.outsider,
            is_personal=False,
        )
        Membership.objects.create(
            organization=self.other_organization,
            user=self.outsider,
            role=Membership.Role.OWNER,
        )
        self.other_website = Website.objects.create(
            owner=self.outsider,
            organization=self.other_organization,
            domain="tenant-b.example",
        )
        self.other_scan = Scan.objects.create(
            website=self.other_website,
            status=Scan.Status.COMPLETED,
        )

    def _auth(self, user: User) -> None:
        self.client.force_authenticate(user=user)

    def _result_ids(self, response) -> list[int]:
        return [item["id"] for item in response.data["results"]]

    # ── Viewer: read everything, mutate nothing ─────────────────────────

    def test_viewer_lists_team_websites(self) -> None:
        self._auth(self.viewer)

        response = self.client.get("/api/v1/websites/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._result_ids(response), [self.website.id])

    def test_viewer_reads_team_website_and_scan_history(self) -> None:
        self._auth(self.viewer)

        self.assertEqual(
            self.client.get(f"/api/v1/websites/{self.website.id}/").status_code,
            status.HTTP_200_OK,
        )
        history = self.client.get(f"/api/v1/scans/?website={self.website.id}")
        self.assertEqual(history.status_code, status.HTTP_200_OK)
        self.assertEqual(self._result_ids(history), [self.scan.id])
        self.assertEqual(
            self.client.get(f"/api/v1/scans/{self.scan.id}/").status_code,
            status.HTTP_200_OK,
        )
        results = self.client.get(f"/api/v1/scans/{self.scan.id}/results/")
        self.assertEqual(results.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results.data["results"]), 1)

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_viewer_cannot_trigger_scan(self, mock_delay) -> None:
        self._auth(self.viewer)

        response = self.client.post(
            f"/api/v1/websites/{self.website.id}/scan/",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            Scan.objects.filter(website=self.website).count(),
            1,
        )
        mock_delay.assert_not_called()

    def test_viewer_cannot_update_or_delete_website(self) -> None:
        self._auth(self.viewer)

        patch_response = self.client.patch(
            f"/api/v1/websites/{self.website.id}/",
            {"display_name": "Hijacked"},
            format="json",
        )
        delete_response = self.client.delete(
            f"/api/v1/websites/{self.website.id}/"
        )

        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Website.objects.filter(pk=self.website.pk).exists())

    def test_viewer_cannot_create_website_in_team(self) -> None:
        self._auth(self.viewer)

        response = self.client.post(
            "/api/v1/websites/",
            {
                "domain": "viewer-created.example",
                "organization_id": str(self.organization.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            Website.objects.filter(domain="viewer-created.example").exists()
        )

    # ── Analyst / Admin / Owner writes ──────────────────────────────────

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_analyst_can_trigger_scan_and_update_website(self, mock_delay) -> None:
        self._auth(self.analyst)

        scan_response = self.client.post(
            f"/api/v1/websites/{self.website.id}/scan/",
            format="json",
        )
        patch_response = self.client.patch(
            f"/api/v1/websites/{self.website.id}/",
            {"display_name": "Tenant A main"},
            format="json",
        )

        self.assertEqual(scan_response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        new_scan = Scan.objects.get(pk=scan_response.data["id"])
        self.assertEqual(new_scan.website, self.website)
        mock_delay.assert_called_once_with(new_scan.id)

    def test_analyst_can_create_website_in_team(self) -> None:
        self._auth(self.analyst)

        response = self.client.post(
            "/api/v1/websites/",
            {
                "domain": "analyst-created.example",
                "organization_id": str(self.organization.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Website.objects.get(domain="analyst-created.example")
        self.assertEqual(created.organization, self.organization)
        self.assertEqual(created.owner, self.analyst)

    def test_owner_can_create_website_for_team(self) -> None:
        self._auth(self.owner)

        response = self.client.post(
            "/api/v1/websites/",
            {
                "domain": "owner-created.example",
                "organization_id": str(self.organization.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Website.objects.get(domain="owner-created.example")
        self.assertEqual(created.organization, self.organization)

    def test_analyst_cannot_delete_website(self) -> None:
        self._auth(self.analyst)

        response = self.client.delete(
            f"/api/v1/websites/{self.website.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Website.objects.filter(pk=self.website.pk).exists())

    def test_admin_can_delete_website(self) -> None:
        self._auth(self.admin)

        response = self.client.delete(
            f"/api/v1/websites/{self.website.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Website.objects.filter(pk=self.website.pk).exists())

    def test_same_domain_allowed_in_different_organizations(self) -> None:
        Website.objects.create(
            owner=self.outsider,
            organization=self.other_organization,
            domain="shared-domain.example",
        )
        self._auth(self.owner)

        response = self.client.post(
            "/api/v1/websites/",
            {
                "domain": "shared-domain.example",
                "organization_id": str(self.organization.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_same_domain_rejected_inside_one_organization(self) -> None:
        Website.objects.create(
            owner=self.owner,
            organization=self.organization,
            domain="duplicate-in-team.example",
        )
        self._auth(self.analyst)

        response = self.client.post(
            "/api/v1/websites/",
            {
                "domain": "duplicate-in-team.example",
                "organization_id": str(self.organization.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Strict cross-tenant invisibility ────────────────────────────────

    def test_other_organization_website_and_scan_are_404(self) -> None:
        self._auth(self.viewer)

        self.assertEqual(
            self.client.get(f"/api/v1/websites/{self.other_website.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/scans/{self.other_scan.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/websites/{self.other_website.id}/scan/",
                format="json",
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_scan_list_excludes_other_tenants(self) -> None:
        self._auth(self.analyst)

        response = self.client.get("/api/v1/scans/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self._result_ids(response)
        self.assertIn(self.scan.id, ids)
        self.assertNotIn(self.other_scan.id, ids)

    def test_cross_tenant_check_results_do_not_leak(self) -> None:
        self._auth(self.viewer)

        response = self.client.get(
            f"/api/v1/scans/{self.other_scan.id}/results/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])
