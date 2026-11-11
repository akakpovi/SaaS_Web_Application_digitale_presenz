"""Tests for the progressive journey REST API (Lot D).

The view layer is deliberately thin: every state transition is delegated to
``JourneyService``.  These tests therefore focus on HTTP semantics
(authentication, tenant isolation, role matrix, status codes, payload shape)
and on the fact that the existing service contract is exposed unchanged.
"""

from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from organizations.models import Membership
from scans.models import JourneyState, Scan, ScanJourney
from subscriptions.models import Plan
from websites.models import Website

JOURNEYS_URL = "/api/v1/scan-journeys/"


def _journey_url(journey_id: int) -> str:
    return f"{JOURNEYS_URL}{journey_id}/"


def _advance_url(journey_id: int) -> str:
    return f"{JOURNEYS_URL}{journey_id}/advance/"


def _cancel_url(journey_id: int) -> str:
    return f"{JOURNEYS_URL}{journey_id}/cancel/"


class JourneyAPITestMixin:
    """Shared fixtures: one organization with the four roles plus an outsider."""

    def setUp(self) -> None:
        # The Free plan must exist before the users: the post_save signal then
        # attaches a subscription to each of them, which is what the quota
        # admission reads through the organization's billing owner.
        self.plan = Plan.objects.create(
            tier=Plan.Tier.FREE,
            name="Free API",
            max_scans_per_month=100,
        )
        self.owner = self._user("owner")
        self.website = Website.objects.create(
            owner=self.owner,
            domain="journey-api.example",
        )
        self.organization = self.website.organization

        self.admin = self._member("admin", Membership.Role.ADMIN)
        self.analyst = self._member("analyst", Membership.Role.ANALYST)
        self.viewer = self._member("viewer", Membership.Role.VIEWER)

        self.outsider = self._user("outsider")
        self.outsider_website = Website.objects.create(
            owner=self.outsider,
            domain="journey-api-outsider.example",
        )
        self.superuser = User.objects.create_superuser(
            "journey-api-root@example.com",
            "CorrectHorseBattery1!",
        )

        patcher = mock.patch("scans.tasks.run_authenticated_scan.delay")
        self.delay = patcher.start()
        self.addCleanup(patcher.stop)

        self.client.force_authenticate(user=self.owner)

    @staticmethod
    def _user(prefix: str) -> User:
        return User.objects.create_user(
            f"journey-api-{prefix}@example.com",
            "CorrectHorseBattery1!",
        )

    def _member(self, prefix: str, role: str) -> User:
        user = self._user(prefix)
        Membership.objects.create(
            organization=self.organization,
            user=user,
            role=role,
        )
        return user

    def _website_for(self, prefix: str) -> Website:
        """A second website of the same organization (role matrix tests)."""
        return Website.objects.create(
            owner=self.owner,
            organization=self.organization,
            domain=f"journey-api-{prefix}.example",
        )

    def _journey(
        self,
        *,
        website: Website | None = None,
        state: str = JourneyState.AWAITING_CONFIRMATION,
        current_stage: int = 1,
        expires_at=None,
        requested_by: User | None = None,
    ) -> ScanJourney:
        return ScanJourney.objects.create(
            website=website or self.website,
            requested_by=requested_by or self.owner,
            state=state,
            current_stage=current_stage,
            total_stages=2,
            expires_at=expires_at,
        )

    def _stage_scan(
        self,
        journey: ScanJourney,
        *,
        stage: int | None = None,
        scan_status: str = Scan.Status.COMPLETED,
        quota_charged: bool | None = None,
    ) -> Scan:
        stage = stage or journey.current_stage
        if quota_charged is None:
            quota_charged = stage == 1
        return Scan.objects.create(
            website=journey.website,
            scan_type=Scan.ScanType.SECURITY,
            status=scan_status,
            journey=journey,
            journey_stage=stage,
            quota_charged=quota_charged,
        )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class JourneyCreateAPITests(JourneyAPITestMixin, APITestCase):
    def test_create_returns_201_and_queues_stage_one(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                JOURNEYS_URL, {"website": self.website.id}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["website"], self.website.id)
        self.assertEqual(response.data["state"], JourneyState.RUNNING)
        self.assertEqual(response.data["current_stage"], 1)
        self.assertEqual(response.data["total_stages"], 2)
        self.assertEqual(response.data["website_url"], "https://journey-api.example")
        self.assertEqual(len(response.data["scans"]), 1)
        self.assertEqual(response.data["scans"][0]["journey_stage"], 1)
        self.assertEqual(response.data["scans"][0]["status"], Scan.Status.QUEUED)

        journey = ScanJourney.objects.get(pk=response.data["id"])
        scan = journey.stages.get()
        self.assertEqual(scan.journey_stage, 1)
        self.assertEqual(scan.status, Scan.Status.QUEUED)
        self.assertTrue(scan.quota_charged)
        self.assertEqual(scan.trigger, Scan.Trigger.MANUAL)
        self.delay.assert_called_once_with(scan.id)

    def test_create_requires_website(self) -> None:
        response = self.client.post(JOURNEYS_URL, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("website", response.data)
        self.assertEqual(ScanJourney.objects.count(), 0)

    def test_create_rejects_invalid_website(self) -> None:
        response = self.client.post(
            JOURNEYS_URL, {"website": "not-an-id"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("website", response.data)

    def test_create_rejects_unknown_website(self) -> None:
        response = self.client.post(JOURNEYS_URL, {"website": 999999}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_rejects_foreign_website(self) -> None:
        response = self.client.post(
            JOURNEYS_URL, {"website": self.outsider_website.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(ScanJourney.objects.count(), 0)

    def test_create_requires_authentication(self) -> None:
        self.client.force_authenticate(user=None)

        response = self.client.post(
            JOURNEYS_URL, {"website": self.website.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_viewer_cannot_create(self) -> None:
        self.client.force_authenticate(user=self.viewer)

        response = self.client.post(
            JOURNEYS_URL, {"website": self.website.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ScanJourney.objects.count(), 0)
        self.assertEqual(Scan.objects.count(), 0)

    def test_active_journey_returns_409(self) -> None:
        journey = self._journey()

        response = self.client.post(
            JOURNEYS_URL, {"website": self.website.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["journey_id"], journey.id)
        self.assertEqual(response.data["state"], JourneyState.AWAITING_CONFIRMATION)
        self.assertEqual(ScanJourney.objects.count(), 1)

    def test_quota_exceeded_returns_429(self) -> None:
        Plan.objects.filter(pk=self.plan.pk).update(max_scans_per_month=1)
        Scan.objects.create(website=self.website, status=Scan.Status.COMPLETED)

        response = self.client.post(
            JOURNEYS_URL, {"website": self.website.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data["used"], 1)
        self.assertEqual(response.data["limit"], 1)
        self.assertEqual(ScanJourney.objects.count(), 0)

    def test_double_post_creates_one_journey(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            first = self.client.post(
                JOURNEYS_URL, {"website": self.website.id}, format="json"
            )
            second = self.client.post(
                JOURNEYS_URL, {"website": self.website.id}, format="json"
            )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(ScanJourney.objects.count(), 1)
        self.assertEqual(Scan.objects.count(), 1)
        self.delay.assert_called_once()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class JourneyListAPITests(JourneyAPITestMixin, APITestCase):
    def test_list_returns_only_organization_journeys(self) -> None:
        own = self._journey(website=self.website)
        self._journey(
            website=self.outsider_website,
            requested_by=self.outsider,
        )

        response = self.client.get(JOURNEYS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [own.id])

    def test_list_filters_by_website(self) -> None:
        first = self._journey(website=self._website_for("filter-a"))
        self._journey(website=self._website_for("filter-b"))

        response = self.client.get(JOURNEYS_URL, {"website": first.website_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [first.id])

    def test_list_filters_by_state(self) -> None:
        self._journey(
            website=self._website_for("state-running"),
            state=JourneyState.RUNNING,
        )
        completed = self._journey(
            website=self._website_for("state-completed"),
            state=JourneyState.COMPLETED,
        )

        response = self.client.get(JOURNEYS_URL, {"state": JourneyState.COMPLETED})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [completed.id])

    def test_superuser_sees_all_journeys(self) -> None:
        own = self._journey(website=self.website)
        foreign = self._journey(
            website=self.outsider_website,
            requested_by=self.outsider,
        )
        self.client.force_authenticate(user=self.superuser)

        response = self.client.get(JOURNEYS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {own.id, foreign.id})

    def test_list_uses_standard_pagination(self) -> None:
        self._journey()

        response = self.client.get(JOURNEYS_URL)

        self.assertEqual(
            set(response.data.keys()),
            {"count", "next", "previous", "results"},
        )
        self.assertEqual(response.data["count"], 1)

    def test_list_requires_authentication(self) -> None:
        self.client.force_authenticate(user=None)

        response = self.client.get(JOURNEYS_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_viewer_can_list(self) -> None:
        journey = self._journey()
        self.client.force_authenticate(user=self.viewer)

        response = self.client.get(JOURNEYS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["id"], journey.id)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class JourneyDetailAPITests(JourneyAPITestMixin, APITestCase):
    def test_detail_returns_journey_and_stages(self) -> None:
        journey = self._journey()
        scan = self._stage_scan(journey, scan_status=Scan.Status.COMPLETED)

        response = self.client.get(_journey_url(journey.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], journey.id)
        self.assertEqual(response.data["requested_by"], self.owner.id)
        self.assertEqual(response.data["website_url"], "https://journey-api.example")
        self.assertEqual(len(response.data["scans"]), 1)
        self.assertEqual(response.data["scans"][0]["id"], scan.id)
        self.assertEqual(response.data["scans"][0]["journey_stage"], 1)
        self.assertEqual(response.data["scans"][0]["status"], Scan.Status.COMPLETED)
        self.assertTrue(response.data["scans"][0]["quota_charged"])

    def test_detail_contains_expected_fields(self) -> None:
        journey = self._journey()

        response = self.client.get(_journey_url(journey.id))

        self.assertEqual(
            set(response.data.keys()),
            {
                "id",
                "website",
                "website_url",
                "requested_by",
                "state",
                "current_stage",
                "total_stages",
                "expires_at",
                "created_at",
                "updated_at",
                "scans",
            },
        )

    def test_detail_hides_other_organizations(self) -> None:
        foreign = self._journey(
            website=self.outsider_website,
            requested_by=self.outsider,
        )

        response = self.client.get(_journey_url(foreign.id))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_unknown_is_404(self) -> None:
        response = self.client.get(_journey_url(999999))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_requires_authentication(self) -> None:
        journey = self._journey()
        self.client.force_authenticate(user=None)

        response = self.client.get(_journey_url(journey.id))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_viewer_can_read(self) -> None:
        journey = self._journey()
        self.client.force_authenticate(user=self.viewer)

        response = self.client.get(_journey_url(journey.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class JourneyAdvanceAPITests(JourneyAPITestMixin, APITestCase):
    @override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=True)
    def test_advance_creates_stage_two(self) -> None:
        journey = self._journey(expires_at=timezone.now() + timedelta(hours=1))
        self._stage_scan(journey, stage=1, scan_status=Scan.Status.COMPLETED)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(_advance_url(journey.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["state"], JourneyState.RUNNING)
        self.assertEqual(response.data["current_stage"], 2)

        stage_two = Scan.objects.get(journey=journey, journey_stage=2)
        self.assertEqual(stage_two.status, Scan.Status.QUEUED)
        self.assertFalse(stage_two.quota_charged)
        self.delay.assert_called_once_with(stage_two.id)

    def test_advance_running_returns_400(self) -> None:
        journey = self._journey(state=JourneyState.RUNNING)

        response = self.client.post(_advance_url(journey.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["current_state"], JourneyState.RUNNING)
        self.assertFalse(Scan.objects.filter(journey=journey, journey_stage=2).exists())

    def test_advance_completed_returns_400(self) -> None:
        journey = self._journey(state=JourneyState.COMPLETED)

        response = self.client.post(_advance_url(journey.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["current_state"], JourneyState.COMPLETED)

    def test_advance_expired_returns_410(self) -> None:
        expired_at = timezone.now() - timedelta(hours=1)
        journey = self._journey(expires_at=expired_at)

        response = self.client.post(_advance_url(journey.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertIsNotNone(response.data["expired_at"])
        self.assertFalse(Scan.objects.filter(journey=journey, journey_stage=2).exists())

    def test_advance_conflict_with_classic_scan_returns_409(self) -> None:
        journey = self._journey(expires_at=timezone.now() + timedelta(hours=1))
        self._stage_scan(journey, stage=1, scan_status=Scan.Status.COMPLETED)
        Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)

        response = self.client.post(_advance_url(journey.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(Scan.objects.filter(journey=journey, journey_stage=2).exists())

    @override_settings(SCANNER_ADVANCED_SECURITY_ENABLED=False)
    def test_advance_without_nuclei_marks_journey_failed(self) -> None:
        journey = self._journey(expires_at=timezone.now() + timedelta(hours=1))

        response = self.client.post(_advance_url(journey.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["state"], JourneyState.FAILED)
        self.assertFalse(Scan.objects.filter(journey=journey, journey_stage=2).exists())

    def test_viewer_cannot_advance(self) -> None:
        journey = self._journey()
        self.client.force_authenticate(user=self.viewer)

        response = self.client.post(_advance_url(journey.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Scan.objects.filter(journey=journey).count(), 0)

    def test_foreign_journey_is_404(self) -> None:
        foreign = self._journey(
            website=self.outsider_website,
            requested_by=self.outsider,
        )

        response = self.client.post(_advance_url(foreign.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_advance_requires_authentication(self) -> None:
        journey = self._journey()
        self.client.force_authenticate(user=None)

        response = self.client.post(_advance_url(journey.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class JourneyCancelAPITests(JourneyAPITestMixin, APITestCase):
    def test_cancel_awaiting_journey(self) -> None:
        journey = self._journey()
        scan = self._stage_scan(journey, scan_status=Scan.Status.QUEUED)

        response = self.client.post(_cancel_url(journey.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["state"], JourneyState.CANCELLED)
        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.CANCELLED)

    def test_cancel_running_journey(self) -> None:
        journey = self._journey(state=JourneyState.RUNNING)
        scan = self._stage_scan(journey, scan_status=Scan.Status.RUNNING)

        response = self.client.post(_cancel_url(journey.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["state"], JourneyState.CANCELLED)
        scan.refresh_from_db()
        self.assertEqual(scan.status, Scan.Status.CANCELLED)

    def test_cancel_completed_returns_400(self) -> None:
        journey = self._journey(state=JourneyState.COMPLETED)

        response = self.client.post(_cancel_url(journey.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["current_state"], JourneyState.COMPLETED)

    def test_second_cancel_returns_400(self) -> None:
        journey = self._journey()

        first = self.client.post(_cancel_url(journey.id), {}, format="json")
        second = self.client.post(_cancel_url(journey.id), {}, format="json")

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_viewer_forbidden(self) -> None:
        journey = self._journey()
        self.client.force_authenticate(user=self.viewer)

        response = self.client.post(_cancel_url(journey.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        journey.refresh_from_db()
        self.assertEqual(journey.state, JourneyState.AWAITING_CONFIRMATION)

    def test_cancel_foreign_journey_is_404(self) -> None:
        foreign = self._journey(
            website=self.outsider_website,
            requested_by=self.outsider,
        )

        response = self.client.post(_cancel_url(foreign.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_requires_authentication(self) -> None:
        journey = self._journey()
        self.client.force_authenticate(user=None)

        response = self.client.post(_cancel_url(journey.id), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class JourneyPermissionMatrixAPITests(JourneyAPITestMixin, APITestCase):
    def test_admin_can_create(self) -> None:
        website = self._website_for("admin-create")
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            JOURNEYS_URL, {"website": website.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["website"], website.id)

    def test_analyst_can_create(self) -> None:
        website = self._website_for("analyst-create")
        self.client.force_authenticate(user=self.analyst)

        response = self.client.post(
            JOURNEYS_URL, {"website": website.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["website"], website.id)

    def test_superuser_can_create_on_foreign_website(self) -> None:
        self.client.force_authenticate(user=self.superuser)

        response = self.client.post(
            JOURNEYS_URL, {"website": self.outsider_website.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_superuser_can_retrieve_foreign_journey(self) -> None:
        foreign = self._journey(
            website=self.outsider_website,
            requested_by=self.outsider,
        )
        self.client.force_authenticate(user=self.superuser)

        response = self.client.get(_journey_url(foreign.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_outsider_cannot_create(self) -> None:
        self.client.force_authenticate(user=self.outsider)

        response = self.client.post(
            JOURNEYS_URL, {"website": self.website.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
