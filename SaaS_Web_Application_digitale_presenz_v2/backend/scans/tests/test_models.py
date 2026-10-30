"""Model-level tests for ScanJourney and its link to Scan."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from scans.models import JourneyState, Scan, ScanJourney
from websites.models import Website


class ScanJourneyModelTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            "journey-owner@example.com", "CorrectHorseBattery1!"
        )
        self.website = Website.objects.create(
            owner=self.user, domain="journey.example"
        )

    def _journey(self, **kwargs) -> ScanJourney:
        defaults = {
            "website": self.website,
            "requested_by": self.user,
            "expires_at": timezone.now() + timedelta(hours=24),
        }
        defaults.update(kwargs)
        return ScanJourney.objects.create(**defaults)

    # ── Valid creation ──

    def test_journey_defaults_and_child_scan(self) -> None:
        journey = self._journey()

        self.assertEqual(journey.state, JourneyState.RUNNING)
        self.assertEqual(journey.current_stage, 1)
        self.assertEqual(journey.total_stages, 2)
        self.assertEqual(journey.requested_by, self.user)
        self.assertIsNotNone(journey.expires_at)

        scan = Scan.objects.create(
            website=self.website,
            journey=journey,
            journey_stage=1,
        )

        self.assertEqual(scan.journey, journey)
        self.assertEqual(scan.journey_stage, 1)
        self.assertTrue(scan.quota_charged)
        self.assertEqual(list(journey.stages.all()), [scan])

    def test_scan_quota_charged_defaults_to_true_without_journey(self) -> None:
        scan = Scan.objects.create(website=self.website)

        self.assertIsNone(scan.journey)
        self.assertIsNone(scan.journey_stage)
        self.assertTrue(scan.quota_charged)

    # ── Unique active journey per website ──

    def test_second_active_journey_is_rejected(self) -> None:
        self._journey(state=JourneyState.RUNNING)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._journey(state=JourneyState.AWAITING_CONFIRMATION)

    def test_finished_journey_does_not_block_a_new_one(self) -> None:
        self._journey(state=JourneyState.COMPLETED)

        active = self._journey(state=JourneyState.RUNNING)

        self.assertEqual(
            ScanJourney.objects.filter(website=self.website).count(), 2
        )
        self.assertEqual(active.state, JourneyState.RUNNING)

    # ── One scan per journey stage ──

    def test_duplicate_scan_for_the_same_stage_is_rejected(self) -> None:
        journey = self._journey()
        Scan.objects.create(
            website=self.website, journey=journey, journey_stage=1
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Scan.objects.create(
                    website=self.website,
                    journey=journey,
                    journey_stage=1,
                )

    # ── Journey/stage consistency ──

    def test_scan_with_journey_requires_a_stage(self) -> None:
        journey = self._journey()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Scan.objects.create(website=self.website, journey=journey)

    def test_scan_with_stage_requires_a_journey(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Scan.objects.create(website=self.website, journey_stage=1)

    def test_scan_without_journey_or_stage_is_valid(self) -> None:
        scan = Scan.objects.create(website=self.website)

        self.assertIsNone(scan.journey)
        self.assertIsNone(scan.journey_stage)

    # ── Stage range ──

    def test_current_stage_above_total_stages_is_rejected(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._journey(current_stage=3, total_stages=2)

    def test_current_stage_below_one_is_rejected(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._journey(current_stage=0, total_stages=2)

    def test_last_stage_is_accepted(self) -> None:
        journey = self._journey(current_stage=2, total_stages=2)

        self.assertEqual(journey.current_stage, 2)

    # ── Cascade ──

    def test_deleting_journey_deletes_its_stage_scans(self) -> None:
        journey = self._journey()
        scan = Scan.objects.create(
            website=self.website, journey=journey, journey_stage=1
        )

        journey.delete()

        self.assertFalse(Scan.objects.filter(pk=scan.pk).exists())
