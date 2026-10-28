"""Phase F regression tests for organization team management."""

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from organizations.models import Membership, Organization, OrganizationInvitation
from subscriptions.models import Plan, Subscription
from websites.models import Website


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class TeamManagementAPITests(APITestCase):
    def setUp(self) -> None:
        # Create Free first so new users receive the normal default
        # subscription, then upgrade the organization owner to Business.
        self.free_plan = Plan.objects.create(
            tier=Plan.Tier.FREE,
            name="Free",
            max_websites=1,
            max_scans_per_month=10,
            max_team_members=1,
            can_add_team_members=False,
        )
        self.business_plan = Plan.objects.create(
            tier=Plan.Tier.BUSINESS,
            name="Business",
            max_websites=20,
            max_scans_per_month=1000,
            max_team_members=5,
            can_add_team_members=True,
        )

        self.owner = User.objects.create_user("owner@team.example", "Password123!")
        self.admin = User.objects.create_user("admin@team.example", "Password123!")
        self.analyst = User.objects.create_user("analyst@team.example", "Password123!")
        self.viewer = User.objects.create_user("viewer@team.example", "Password123!")
        self.outsider = User.objects.create_user("outsider@other.example", "Password123!")

        Subscription.objects.update_or_create(
            user=self.owner,
            defaults={
                "plan": self.business_plan,
                "status": Subscription.Status.ACTIVE,
            },
        )

        self.organization = Organization.objects.create(
            name="Team Presence",
            billing_owner=self.owner,
            is_personal=False,
        )
        self.owner_membership = Membership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=Membership.Role.OWNER,
        )
        self.admin_membership = Membership.objects.create(
            organization=self.organization,
            user=self.admin,
            role=Membership.Role.ADMIN,
        )
        self.analyst_membership = Membership.objects.create(
            organization=self.organization,
            user=self.analyst,
            role=Membership.Role.ANALYST,
        )
        self.viewer_membership = Membership.objects.create(
            organization=self.organization,
            user=self.viewer,
            role=Membership.Role.VIEWER,
        )
        self.website = Website.objects.create(
            owner=self.owner,
            organization=self.organization,
            domain="team-presence.example",
        )

        self.other_organization = Organization.objects.create(
            name="Other Tenant",
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
            domain="other-tenant.example",
        )

    def _auth(self, user: User) -> None:
        self.client.force_authenticate(user=user)

    def _members_url(self, organization: Organization | None = None) -> str:
        organization = organization or self.organization
        return f"/api/v1/organizations/{organization.id}/members/"

    def _invitations_url(self, organization: Organization | None = None) -> str:
        organization = organization or self.organization
        return f"/api/v1/organizations/{organization.id}/invitations/"

    # ── Organization + member reads ─────────────────────────────────────

    def test_organization_list_exposes_caller_role(self) -> None:
        self._auth(self.viewer)

        response = self.client.get("/api/v1/organizations/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = (
            response.data["results"]
            if isinstance(response.data, dict)
            else response.data
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], str(self.organization.id))
        self.assertEqual(items[0]["role"], Membership.Role.VIEWER)
        self.assertEqual(items[0]["member_count"], 4)

    def test_viewer_can_list_members(self) -> None:
        self._auth(self.viewer)

        response = self.client.get(self._members_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        roles = {member["email"]: member["role"] for member in response.data}
        self.assertEqual(roles["owner@team.example"], Membership.Role.OWNER)
        self.assertEqual(roles["admin@team.example"], Membership.Role.ADMIN)
        self.assertEqual(roles["analyst@team.example"], Membership.Role.ANALYST)
        self.assertEqual(roles["viewer@team.example"], Membership.Role.VIEWER)

    def test_non_member_gets_404_for_members(self) -> None:
        self._auth(self.outsider)

        response = self.client.get(self._members_url())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ── Role enforcement ────────────────────────────────────────────────

    def test_viewer_cannot_manage_members(self) -> None:
        self._auth(self.viewer)

        self.assertEqual(
            self.client.post(
                self._members_url(),
                {"email": "new@team.example", "role": "viewer"},
                format="json",
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.patch(
                f"{self._members_url()}{self.analyst_membership.id}/",
                {"role": "viewer"},
                format="json",
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.delete(
                f"{self._members_url()}{self.analyst_membership.id}/"
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_admin_can_invite_analyst_but_cannot_grant_admin(self) -> None:
        candidate = User.objects.create_user("candidate@team.example", "Password123!")
        self._auth(self.admin)

        response = self.client.post(
            self._members_url(),
            {"email": candidate.email, "role": "analyst"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Membership.objects.filter(
                organization=self.organization,
                user=candidate,
                role=Membership.Role.ANALYST,
            ).exists()
        )

        second = User.objects.create_user("second@team.example", "Password123!")
        response = self.client.post(
            self._members_url(),
            {"email": second.email, "role": "admin"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            Membership.objects.filter(
                organization=self.organization,
                user=second,
            ).exists()
        )

    def test_owner_can_add_admin(self) -> None:
        candidate = User.objects.create_user("paid-admin@team.example", "Password123!")
        self._auth(self.owner)

        response = self.client.post(
            self._members_url(),
            {"email": candidate.email, "role": "admin"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Membership.objects.filter(
                organization=self.organization,
                user=candidate,
                role=Membership.Role.ADMIN,
            ).exists()
        )

    def test_owner_can_change_role_and_remove_member(self) -> None:
        self._auth(self.owner)
        detail_url = f"{self._members_url()}{self.viewer_membership.id}/"

        response = self.client.patch(detail_url, {"role": "analyst"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.viewer_membership.refresh_from_db()
        self.assertEqual(self.viewer_membership.role, Membership.Role.ANALYST)

        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Membership.objects.filter(pk=self.viewer_membership.pk).exists()
        )

    def test_admin_cannot_change_owner_or_another_admin(self) -> None:
        self._auth(self.admin)

        owner_response = self.client.patch(
            f"{self._members_url()}{self.owner_membership.id}/",
            {"role": "viewer"},
            format="json",
        )
        self.assertEqual(owner_response.status_code, status.HTTP_403_FORBIDDEN)

        admin_response = self.client.patch(
            f"{self._members_url()}{self.admin_membership.id}/",
            {"role": "viewer"},
            format="json",
        )
        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)

        self.owner_membership.refresh_from_db()
        self.admin_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.role, Membership.Role.OWNER)
        self.assertEqual(self.admin_membership.role, Membership.Role.ADMIN)

    def test_adding_existing_member_is_a_conflict(self) -> None:
        self._auth(self.owner)

        response = self.client.post(
            self._members_url(),
            {"email": self.analyst.email, "role": "viewer"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    # ── Pending invitations ─────────────────────────────────────────────

    def test_invitation_for_user_without_account_then_acceptance(self) -> None:
        self._auth(self.owner)
        email = "future@team.example"

        response = self.client.post(
            self._members_url(),
            {"email": email, "role": "analyst"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["status"], "invited")
        self.assertTrue(response.data["email_sent"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Team Presence", mail.outbox[0].subject)
        self.assertIn(email, mail.outbox[0].to)

        invitation = OrganizationInvitation.objects.get(
            organization=self.organization,
            email=email,
        )
        self.assertEqual(invitation.status, OrganizationInvitation.Status.PENDING)
        self.assertEqual(len(invitation.token_hash), 64)

        token = parse_qs(urlparse(response.data["accept_url"]).query)["token"][0]
        self.assertNotIn(token, invitation.token_hash)

        future_user = User.objects.create_user(email, "Password123!")
        self._auth(future_user)
        accept_response = self.client.post(
            f"/api/v1/organizations/invitations/{token}/accept/"
        )

        self.assertEqual(accept_response.status_code, status.HTTP_200_OK)
        self.assertEqual(accept_response.data["role"], Membership.Role.ANALYST)
        self.assertTrue(
            Membership.objects.filter(
                organization=self.organization,
                user=future_user,
                role=Membership.Role.ANALYST,
            ).exists()
        )
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.ACCEPTED)
        self.assertIsNotNone(invitation.accepted_at)

    def test_owner_can_list_and_revoke_pending_invitation(self) -> None:
        self._auth(self.owner)
        self.client.post(
            self._members_url(),
            {"email": "revoked@team.example", "role": "viewer"},
            format="json",
        )
        invitation = OrganizationInvitation.objects.get(email="revoked@team.example")

        list_response = self.client.get(self._invitations_url())
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)

        revoke_response = self.client.delete(
            f"{self._invitations_url()}{invitation.id}/"
        )
        self.assertEqual(revoke_response.status_code, status.HTTP_204_NO_CONTENT)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.REVOKED)

        revoked_user = User.objects.create_user(
            "revoked@team.example",
            "Password123!",
        )
        self._auth(revoked_user)
        token = parse_qs(urlparse(mail.outbox[0].body.split("Accept the invitation: ")[1].split()[0]).query)["token"][0]
        self.assertEqual(
            self.client.post(
                f"/api/v1/organizations/invitations/{token}/accept/"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_viewer_cannot_list_invitations(self) -> None:
        self._auth(self.viewer)

        response = self.client.get(self._invitations_url())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invitation_email_mismatch_is_rejected(self) -> None:
        self._auth(self.owner)
        self.client.post(
            self._members_url(),
            {"email": "intended@team.example", "role": "viewer"},
            format="json",
        )
        invitation = OrganizationInvitation.objects.get(email="intended@team.example")
        token = parse_qs(urlparse(mail.outbox[0].body.split("Accept the invitation: ")[1].split()[0]).query)["token"][0]

        wrong_user = User.objects.create_user("wrong@team.example", "Password123!")
        self._auth(wrong_user)
        response = self.client.post(
            f"/api/v1/organizations/invitations/{token}/accept/"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            Membership.objects.filter(
                organization=self.organization,
                user=wrong_user,
            ).exists()
        )
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.PENDING)

    def test_expired_invitation_is_rejected(self) -> None:
        self._auth(self.owner)
        self.client.post(
            self._members_url(),
            {"email": "late@team.example", "role": "analyst"},
            format="json",
        )
        invitation = OrganizationInvitation.objects.get(email="late@team.example")
        token = parse_qs(urlparse(mail.outbox[0].body.split("Accept the invitation: ")[1].split()[0]).query)["token"][0]
        invitation.expires_at = timezone.now() - timedelta(minutes=1)
        invitation.save(update_fields=["expires_at"])

        late_user = User.objects.create_user("late@team.example", "Password123!")
        self._auth(late_user)
        response = self.client.post(
            f"/api/v1/organizations/invitations/{token}/accept/"
        )

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertFalse(
            Membership.objects.filter(
                organization=self.organization,
                user=late_user,
            ).exists()
        )
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.Status.EXPIRED)

    # ── Plan limits ─────────────────────────────────────────────────────

    def test_pending_invitations_reserve_seats(self) -> None:
        Plan.objects.filter(pk=self.business_plan.pk).update(max_team_members=5)
        self._auth(self.owner)

        first = self.client.post(
            self._members_url(),
            {"email": "first-pending@team.example", "role": "viewer"},
            format="json",
        )
        second = self.client.post(
            self._members_url(),
            {"email": "second-pending@team.example", "role": "viewer"},
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(second.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(second.data["code"], "team_member_limit_reached")

    def test_free_plan_cannot_add_team_members(self) -> None:
        Subscription.objects.filter(user=self.owner).update(plan=self.free_plan)
        self._auth(self.owner)

        response = self.client.post(
            self._members_url(),
            {"email": "blocked@team.example", "role": "viewer"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "team_members_not_allowed")
