"""Comprehensive Phase 4 tests for the Website domain.

Tests cover:
- Website CRUD operations
- Domain normalization and validation
- Ownership isolation (User A cannot access User B's websites)
- Unauthenticated access rejection
- Asynchronous manual scan creation via website endpoint
- Prevention of concurrent scans
- is_active field handling
"""

from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from scans.models import Scan
from websites.models import Website


@override_settings(
    PASSWORD_HASHERS=[
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]
)
class WebsiteAPITests(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            "owner@example.com",
            "CorrectHorseBattery1!",
        )
        self.other_user = User.objects.create_user(
            "other@example.com",
            "CorrectHorseBattery1!",
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=(
                f"Bearer {AccessToken.for_user(self.user)}"
            )
        )

    # ──────────────────────────────────────────────
    # Creation
    # ──────────────────────────────────────────────

    def test_owner_can_create_normalized_website(self) -> None:
        response = self.client.post(
            "/api/v1/websites/",
            {
                "domain": " Example.COM. ",
                "display_name": "Main site",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data["domain"],
            "example.com",
        )
        self.assertEqual(
            response.data["display_name"],
            "Main site",
        )
        self.assertTrue(
            response.data["is_active"]
        )

        self.assertEqual(
            Website.objects.get().owner,
            self.user,
        )

    def test_create_website_defaults_is_active_to_true(self) -> None:
        response = self.client.post(
            "/api/v1/websites/",
            {"domain": "active.example"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertTrue(
            response.data["is_active"]
        )

    def test_create_website_with_is_active_false(self) -> None:
        response = self.client.post(
            "/api/v1/websites/",
            {
                "domain": "inactive.example",
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertFalse(
            response.data["is_active"]
        )

    # ──────────────────────────────────────────────
    # Validation — domain format
    # ──────────────────────────────────────────────

    def test_rejects_url_with_scheme(self) -> None:
        response = self.client.post(
            "/api/v1/websites/",
            {"domain": "https://example.com"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_rejects_url_with_path(self) -> None:
        response = self.client.post(
            "/api/v1/websites/",
            {"domain": "example.com/path"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_rejects_url_with_port(self) -> None:
        response = self.client.post(
            "/api/v1/websites/",
            {"domain": "example.com:8080"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_rejects_empty_domain(self) -> None:
        response = self.client.post(
            "/api/v1/websites/",
            {"domain": ""},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_rejects_missing_domain(self) -> None:
        response = self.client.post(
            "/api/v1/websites/",
            {"display_name": "No domain"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    # ──────────────────────────────────────────────
    # Validation — duplicate domains
    # ──────────────────────────────────────────────

    def test_rejects_duplicate_domain_for_same_owner(self) -> None:
        Website.objects.create(
            owner=self.user,
            domain="example.com",
        )

        response = self.client.post(
            "/api/v1/websites/",
            {"domain": "EXAMPLE.COM"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_allows_same_domain_for_different_owners(self) -> None:
        Website.objects.create(
            owner=self.other_user,
            domain="shared.example",
        )

        response = self.client.post(
            "/api/v1/websites/",
            {"domain": "shared.example"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    # ──────────────────────────────────────────────
    # Listing
    # ──────────────────────────────────────────────

    def test_list_returns_only_owned_websites(self) -> None:
        owned = Website.objects.create(
            owner=self.user,
            domain="owned.example",
        )

        Website.objects.create(
            owner=self.other_user,
            domain="other.example",
        )

        response = self.client.get(
            "/api/v1/websites/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        ids = [
            item["id"]
            for item in response.data["results"]
        ]

        self.assertEqual(
            ids,
            [owned.id],
        )

    def test_list_empty_for_user_with_no_websites(self) -> None:
        response = self.client.get(
            "/api/v1/websites/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["results"],
            [],
        )

    # ──────────────────────────────────────────────
    # Retrieval
    # ──────────────────────────────────────────────

    def test_owner_can_retrieve_own_website(self) -> None:
        owned = Website.objects.create(
            owner=self.user,
            domain="mine.example",
            display_name="Mine",
        )

        response = self.client.get(
            f"/api/v1/websites/{owned.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["domain"],
            "mine.example",
        )
        self.assertEqual(
            response.data["display_name"],
            "Mine",
        )

    def test_cannot_retrieve_another_users_website(self) -> None:
        other = Website.objects.create(
            owner=self.other_user,
            domain="secret.example",
        )

        response = self.client.get(
            f"/api/v1/websites/{other.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_retrieve_nonexistent_website_returns_404(self) -> None:
        response = self.client.get(
            "/api/v1/websites/99999/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # ──────────────────────────────────────────────
    # Update
    # ──────────────────────────────────────────────

    def test_owner_can_update_display_name(self) -> None:
        website = Website.objects.create(
            owner=self.user,
            domain="update.example",
            display_name="Old Name",
        )

        response = self.client.patch(
            f"/api/v1/websites/{website.id}/",
            {"display_name": "New Name"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["display_name"],
            "New Name",
        )

    def test_owner_can_update_domain(self) -> None:
        website = Website.objects.create(
            owner=self.user,
            domain="old.example",
        )

        response = self.client.patch(
            f"/api/v1/websites/{website.id}/",
            {"domain": "new.example"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["domain"],
            "new.example",
        )

    def test_owner_can_deactivate_website(self) -> None:
        website = Website.objects.create(
            owner=self.user,
            domain="deactivate.example",
        )

        response = self.client.patch(
            f"/api/v1/websites/{website.id}/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertFalse(
            response.data["is_active"]
        )

    def test_update_domain_to_duplicate_rejected(self) -> None:
        Website.objects.create(
            owner=self.user,
            domain="taken.example",
        )

        website = Website.objects.create(
            owner=self.user,
            domain="other.example",
        )

        response = self.client.patch(
            f"/api/v1/websites/{website.id}/",
            {"domain": "taken.example"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cannot_update_another_users_website(self) -> None:
        other = Website.objects.create(
            owner=self.other_user,
            domain="notmine.example",
        )

        response = self.client.patch(
            f"/api/v1/websites/{other.id}/",
            {"display_name": "Hacked"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # ──────────────────────────────────────────────
    # Deletion
    # ──────────────────────────────────────────────

    def test_owner_can_delete_own_website(self) -> None:
        website = Website.objects.create(
            owner=self.user,
            domain="delete.example",
        )

        response = self.client.delete(
            f"/api/v1/websites/{website.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(
            Website.objects.filter(
                pk=website.id
            ).exists()
        )

    def test_cannot_delete_another_users_website(self) -> None:
        other = Website.objects.create(
            owner=self.other_user,
            domain="protected.example",
        )

        response = self.client.delete(
            f"/api/v1/websites/{other.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertTrue(
            Website.objects.filter(
                pk=other.id
            ).exists()
        )

    def test_deleting_website_cascades_to_scans(self) -> None:
        website = Website.objects.create(
            owner=self.user,
            domain="cascade.example",
        )

        Scan.objects.create(
            website=website,
            status=Scan.Status.QUEUED,
        )

        self.client.delete(
            f"/api/v1/websites/{website.id}/"
        )

        self.assertFalse(
            Scan.objects.filter(
                website=website
            ).exists()
        )

    # ──────────────────────────────────────────────
    # Authentication
    # ──────────────────────────────────────────────

    def test_unauthenticated_access_is_rejected(self) -> None:
        self.client.credentials()

        self.assertEqual(
            self.client.get(
                "/api/v1/websites/"
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            self.client.post(
                "/api/v1/websites/",
                {"domain": "test.example"},
                format="json",
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # ──────────────────────────────────────────────
    # Manual asynchronous scan creation
    # ──────────────────────────────────────────────

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_manual_scan_creation_is_owner_scoped_and_queued(
        self,
        mock_delay,
    ) -> None:
        website = Website.objects.create(
            owner=self.user,
            domain="owned.example",
        )

        response = self.client.post(
            f"/api/v1/websites/{website.id}/scan/",
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_202_ACCEPTED,
        )

        scan = Scan.objects.get()

        self.assertEqual(
            scan.website,
            website,
        )
        self.assertEqual(
            scan.status,
            Scan.Status.QUEUED,
        )
        self.assertEqual(
            scan.trigger,
            Scan.Trigger.MANUAL,
        )

        self.assertEqual(
            response.data["health_status"],
            "neutral",
        )
        self.assertIsNone(
            response.data["health_score"],
        )

        mock_delay.assert_called_once_with(
            scan.id,
        )

    def test_manual_scan_blocked_for_other_users_website(self) -> None:
        other_website = Website.objects.create(
            owner=self.other_user,
            domain="other.example",
        )

        response = self.client.post(
            f"/api/v1/websites/{other_website.id}/scan/",
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_manual_scan_rejects_duplicate_active_scan(
        self,
        mock_delay,
    ) -> None:
        website = Website.objects.create(
            owner=self.user,
            domain="active.example",
        )

        existing_scan = Scan.objects.create(
            website=website,
            trigger=Scan.Trigger.MANUAL,
            status=Scan.Status.RUNNING,
        )

        response = self.client.post(
            f"/api/v1/websites/{website.id}/scan/",
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

        self.assertEqual(
            Scan.objects.filter(
                website=website,
            ).count(),
            1,
        )

        self.assertTrue(
            Scan.objects.filter(
                pk=existing_scan.pk
            ).exists()
        )

        mock_delay.assert_not_called()

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_manual_scan_rejects_pending_scan(
        self,
        mock_delay,
    ) -> None:
        website = Website.objects.create(
            owner=self.user,
            domain="pending.example",
        )

        Scan.objects.create(
            website=website,
            trigger=Scan.Trigger.MANUAL,
            status=Scan.Status.PENDING,
        )

        response = self.client.post(
            f"/api/v1/websites/{website.id}/scan/",
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )
        mock_delay.assert_not_called()

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_manual_scan_rejects_queued_scan(
        self,
        mock_delay,
    ) -> None:
        website = Website.objects.create(
            owner=self.user,
            domain="queued.example",
        )

        Scan.objects.create(
            website=website,
            trigger=Scan.Trigger.MANUAL,
            status=Scan.Status.QUEUED,
        )

        response = self.client.post(
            f"/api/v1/websites/{website.id}/scan/",
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )
        mock_delay.assert_not_called()

    @patch("scans.tasks.run_authenticated_scan.delay")
    def test_terminal_scan_does_not_block_new_manual_scan(
        self,
        mock_delay,
    ) -> None:
        website = Website.objects.create(
            owner=self.user,
            domain="rescan.example",
        )

        previous_scan = Scan.objects.create(
            website=website,
            trigger=Scan.Trigger.MANUAL,
            status=Scan.Status.COMPLETED,
        )

        response = self.client.post(
            f"/api/v1/websites/{website.id}/scan/",
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_202_ACCEPTED,
        )

        self.assertEqual(
            Scan.objects.filter(
                website=website,
            ).count(),
            2,
        )

        new_scan = (
            Scan.objects.filter(
                website=website,
            )
            .exclude(pk=previous_scan.pk)
            .get()
        )

        self.assertEqual(
            new_scan.status,
            Scan.Status.QUEUED,
        )

        mock_delay.assert_called_once_with(
            new_scan.id,
        )

    # ──────────────────────────────────────────────
    # Response format
    # ──────────────────────────────────────────────

    def test_website_response_contains_expected_fields(self) -> None:
        response = self.client.post(
            "/api/v1/websites/",
            {
                "domain": "fields.example",
                "display_name": "Test",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        expected_keys = {
            "id",
            "domain",
            "display_name",
            "is_active",
            "created_at",
            "updated_at",
        }

        self.assertEqual(
            set(response.data.keys()),
            expected_keys,
        )