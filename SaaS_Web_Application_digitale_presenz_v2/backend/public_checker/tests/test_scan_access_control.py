"""Régressions de contrôle d'accès sur les endpoints publics.

Couverture des correctifs P0-03 (IDOR ``/convert/``) et P0-04 (lecture anonyme
des scans privés).  Ces tests échouent si l'un des deux correctifs est retiré.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from scans.models import Scan
from websites.models import Website


class PublicScanAccessControlTests(APITestCase):
    def setUp(self) -> None:
        cache.clear()
        self.user_model = get_user_model()
        self.owner = self.user_model.objects.create_user(
            email="access-owner@example.com", password="Str0ngPass!2026"
        )
        self.attacker = self.user_model.objects.create_user(
            email="access-attacker@example.com", password="Str0ngPass!2026"
        )

        private_site = Website.objects.create(
            owner=self.owner, domain="access-private.example.com", is_guest=False
        )
        self.private_scan = Scan.objects.create(
            website=private_site,
            status=Scan.Status.COMPLETED,
            trigger=Scan.Trigger.MANUAL,
            scan_type=Scan.ScanType.HEALTH,
            health_score=77,
            is_guest=False,
        )

        # Guest scan owned by "visitor" (its session key).
        self.visitor = APITestCase.client_class()
        visitor_session = self.visitor.session
        visitor_session.save()
        self.visitor_session_key = visitor_session.session_key

        guest_site = Website.objects.create(
            domain="access-guest.example.com", is_guest=True
        )
        self.guest_scan = Scan.objects.create(
            website=guest_site,
            status=Scan.Status.COMPLETED,
            trigger=Scan.Trigger.PUBLIC,
            scan_type=Scan.ScanType.HEALTH,
            health_score=64,
            is_guest=True,
            session_key=self.visitor_session_key,
        )

    # ── P0-04 : lecture du rapport ────────────────────────────────────────

    def test_anonymous_cannot_read_private_scan(self):
        response = self.client.get(
            f"/api/v1/public/scan/{self.private_scan.id}/status/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_account_cannot_read_private_scan(self):
        self.client.force_authenticate(user=self.attacker)
        response = self.client.get(
            f"/api/v1/public/scan/{self.private_scan.id}/status/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_read_private_scan(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(
            f"/api/v1/public/scan/{self.private_scan.id}/status/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["score"], 77)

    def test_guest_scan_stays_public(self):
        response = self.client.get(f"/api/v1/public/scan/{self.guest_scan.id}/status/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["score"], 64)

    def test_unknown_numeric_id_is_404(self):
        response = self.client.get("/api/v1/public/scan/999999999/status/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ── P0-03 : conversion d'un scan invité ───────────────────────────────

    def test_foreign_session_cannot_convert_guest_scan(self):
        attacker = APITestCase.client_class()
        attacker.session.save()
        attacker.force_authenticate(user=self.attacker)

        response = attacker.post(f"/api/v1/public/scan/{self.guest_scan.id}/convert/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.guest_scan.refresh_from_db()
        self.assertTrue(self.guest_scan.is_guest)
        self.guest_scan.website.refresh_from_db()
        self.assertIsNone(self.guest_scan.website.owner_id)

    def test_cannot_convert_another_accounts_scan(self):
        self.client.force_authenticate(user=self.attacker)
        response = self.client.post(
            f"/api/v1/public/scan/{self.private_scan.id}/convert/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        self.private_scan.refresh_from_db()
        self.private_scan.website.refresh_from_db()
        self.assertEqual(self.private_scan.website.owner_id, self.owner.pk)

    def test_conversion_requires_authentication(self):
        response = self.client.post(
            f"/api/v1/public/scan/{self.guest_scan.id}/convert/"
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_owner_session_can_convert_its_guest_scan(self):
        self.visitor.force_authenticate(user=self.attacker)

        response = self.visitor.post(
            f"/api/v1/public/scan/{self.guest_scan.id}/convert/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.guest_scan.refresh_from_db()
        self.assertFalse(self.guest_scan.is_guest)
        self.assertIsNone(self.guest_scan.session_key)
        self.guest_scan.website.refresh_from_db()
        self.assertEqual(self.guest_scan.website.owner_id, self.attacker.pk)

    # ── /email/ : pas d'exfiltration de rapport ───────────────────────────

    def test_anonymous_cannot_email_private_scan_report(self):
        response = self.client.post(
            f"/api/v1/public/scan/{self.private_scan.id}/email/",
            {"email": "attacker@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
