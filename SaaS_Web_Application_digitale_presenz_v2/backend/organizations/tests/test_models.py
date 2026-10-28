from django.test import TestCase

from accounts.models import User
from organizations.models import Membership, Organization
from organizations.services import ensure_personal_organization
from websites.models import Website


class OrganizationTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="org-owner@example.com",
            password="pass1234!",
        )

    def test_website_creation_assigns_personal_organization(self) -> None:
        website = Website.objects.create(
            owner=self.user,
            domain="org-owner.example",
        )

        self.assertIsNotNone(website.organization)
        self.assertTrue(website.organization.is_personal)
        self.assertEqual(website.organization.billing_owner, self.user)
        membership = Membership.objects.get(
            organization=website.organization,
            user=self.user,
        )
        self.assertEqual(membership.role, Membership.Role.OWNER)

    def test_personal_organization_is_idempotent(self) -> None:
        first = ensure_personal_organization(self.user)
        second = ensure_personal_organization(self.user)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            Organization.objects.filter(
                billing_owner=self.user,
                is_personal=True,
            ).count(),
            1,
        )
        self.assertEqual(
            Membership.objects.filter(
                organization=first,
                user=self.user,
            ).count(),
            1,
        )

    def test_guest_website_has_no_organization(self) -> None:
        website = Website.objects.create(
            domain="org-guest.example",
            is_guest=True,
        )

        self.assertIsNone(website.organization)
