"""Orchestration of progressive scan journeys.

A :class:`~scans.models.ScanJourney` is a linear, user-confirmed sequence of
regular :class:`~scans.models.Scan` rows.  This module owns the whole state
machine around those child scans:

* :meth:`JourneyService.create_journey` — admission and stage 1 creation;
* :meth:`JourneyService.on_stage_completed` — stage 1 → awaiting confirmation,
  stage 2 → final state;
* :meth:`JourneyService.advance_journey` — explicit user confirmation that
  creates stage 2;
* :meth:`JourneyService.cancel_journey` — terminal cancellation;
* :meth:`JourneyService.check_and_reserve_quota` — atomic quota admission.

Design rules enforced here
--------------------------
* **PostgreSQL is the source of truth.**  Every critical section runs inside a
  ``transaction.atomic()`` block and takes ``select_for_update()`` locks.  No
  Redis lock or Celery singleton is used.
* **Consistent lock order.**  ``Website`` first, then ``ScanJourney``, then
  its child ``Scan`` rows.  Nothing in this module locks them in the reverse
  order, which keeps concurrent creation and advancement deadlock-free.
* **No classic-scan side effects.**  Journey children never touch the health
  score, the monitoring schedule, finding alerts or the AI advisor.  Those
  side effects remain attached to classic scans only (see ``scans/tasks.py``).
* **Option A quota.**  One journey consumes exactly one unit: stage 1 is
  created with ``quota_charged=True`` and stage 2 with ``quota_charged=False``.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .exceptions import (
    JourneyConflictError,
    JourneyExpiredError,
    JourneyStateError,
    QuotaExceededError,
)

logger = logging.getLogger(__name__)

#: Every V1 journey has exactly two stages.
JOURNEY_TOTAL_STAGES = 2

#: Child scans states that still occupy the site / can still be cancelled.
_ACTIVE_SCAN_STATES = ("pending", "queued", "running")

#: Child scans states after which ``on_stage_completed`` may decide.
_TERMINAL_SCAN_STATES = ("completed", "partial", "failed", "cancelled")


def check_write_permission(user: Any, website: Any) -> bool:
    """Return True when *user* may launch a scan on *website*.

    Roles come from the organization membership matrix already used by the
    API (``organizations.access.can_write_website``): owner, admin and analyst
    may write; viewer may not; an outsider has no role at all.  Legacy
    organization-less websites keep their owner as ``owner``.

    Raises:
        PermissionError: when the user has no access or an insufficient role.
    """
    from organizations.access import can_write_website, role_for_website

    if user is None or not getattr(user, "is_authenticated", False):
        raise PermissionError("Authentification requise pour lancer un scan")

    if getattr(user, "is_superuser", False):
        return True

    if can_write_website(user, website):
        return True

    role = role_for_website(user, website)
    if role is None:
        raise PermissionError("Aucun accès à ce site")
    raise PermissionError(f"Rôle {role} insuffisant pour lancer un scan")


class JourneyService:
    """Lifecycle service for progressive scan journeys.

    All methods are class methods so they can be called from tasks, tests and
    (in Lot D) from API views without instantiating anything.
    """

    # ------------------------------------------------------------------
    # Admission
    # ------------------------------------------------------------------

    @classmethod
    @transaction.atomic
    def create_journey(
        cls,
        website: Any,
        requested_by: Any,
        trigger_source: str = "manual",
    ) -> Any:
        """Create a journey and its stage-1 child scan atomically.

        The website row is locked first, which serialises two concurrent
        ``create_journey`` calls for the same site: the second one observes the
        journey created by the first and raises :class:`JourneyConflictError`.
        The organization row is then locked while the monthly quota is checked,
        so two journeys on *different* sites of the same organization cannot
        both consume the last remaining unit.

        The Celery task is published through ``transaction.on_commit``: a
        worker can therefore never observe the scan before its row is visible.

        Args:
            website: ``Website`` instance (must be saved).
            requested_by: user launching the journey.
            trigger_source: ``"manual"``, ``"monitoring"``, ``"onboarding"``
                or ``"public"``.

        Raises:
            PermissionError: the user may not write on this website.
            JourneyConflictError: an active journey already exists.
            QuotaExceededError: the organization's monthly quota is exhausted.
        """
        from scans.models import JourneyState, ScanJourney
        from websites.models import Website

        # Lock the site first: constant lock order (Website → Journey → Scan).
        locked_website = Website.objects.select_for_update().get(pk=website.pk)
        check_write_permission(requested_by, locked_website)

        active_journey = (
            ScanJourney.objects.select_for_update()
            .filter(
                website=locked_website,
                state__in=[
                    JourneyState.RUNNING,
                    JourneyState.AWAITING_CONFIRMATION,
                ],
            )
            .first()
        )
        if active_journey is not None:
            raise JourneyConflictError(
                f"Parcours actif {active_journey.id} en état {active_journey.state}"
            )

        # Quota admission: the organization lock is held until commit, so the
        # count cannot be invalidated by a concurrent creation on a sibling
        # website.  Creating the charged stage-1 scan is the reservation.
        cls.check_and_reserve_quota(locked_website.organization)

        journey = ScanJourney.objects.create(
            website=locked_website,
            requested_by=requested_by,
            state=JourneyState.RUNNING,
            current_stage=1,
            total_stages=JOURNEY_TOTAL_STAGES,
            # No expiry while a stage is executing.
            expires_at=None,
        )

        scan = cls._create_stage_scan(
            journey,
            stage=1,
            quota_charged=True,
            trigger_source=trigger_source,
        )

        cls._publish_stage(scan)

        logger.info(
            "journey_created journey_id=%s website_id=%s stage=1 scan_id=%s trigger=%s",
            journey.pk,
            locked_website.pk,
            scan.pk,
            trigger_source,
        )
        return journey

    # ------------------------------------------------------------------
    # Stage completion
    # ------------------------------------------------------------------

    @classmethod
    @transaction.atomic
    def on_stage_completed(cls, scan_id: int) -> Any | None:
        """Advance the journey after one of its child scans reaches a terminal state.

        Called by :func:`scans.tasks.run_authenticated_scan` once the child scan
        is finalised.  Classic scans (``journey_id IS NULL``) are ignored.

        Stage 1 success (``completed`` or ``partial``) parks the journey in
        ``awaiting_confirmation`` for :data:`SCAN_JOURNEY_TTL_HOURS` hours.
        Stage 1 failure fails the journey.  Stage 2 maps the child status to
        the final journey status.  No health score, monitoring, alert or AI
        side effect is triggered here.

        Idempotent: a duplicate delivery re-reads the journey under a row lock
        and returns it unchanged once it is no longer ``running``.
        """
        from scans.models import JourneyState, Scan, ScanJourney

        journey_id = (
            Scan.objects.filter(pk=scan_id).values_list("journey_id", flat=True).first()
        )
        if journey_id is None:
            return None

        # Journey before its child scan: same order as cancel_journey.
        journey = ScanJourney.objects.select_for_update().get(pk=journey_id)
        scan = Scan.objects.select_for_update().get(pk=scan_id)

        if journey.state != JourneyState.RUNNING:
            logger.info(
                "journey_stage_callback_ignored journey_id=%s state=%s scan_id=%s",
                journey.pk,
                journey.state,
                scan_id,
            )
            return journey

        if scan.status not in _TERMINAL_SCAN_STATES:
            logger.warning(
                "journey_stage_callback_before_terminal journey_id=%s "
                "scan_id=%s status=%s",
                journey.pk,
                scan_id,
                scan.status,
            )
            return journey

        if scan.journey_stage != journey.current_stage:
            logger.warning(
                "journey_stage_mismatch journey_id=%s current_stage=%s "
                "scan_id=%s scan_stage=%s",
                journey.pk,
                journey.current_stage,
                scan_id,
                scan.journey_stage,
            )
            return journey

        previous_state = journey.state

        if journey.current_stage < journey.total_stages:
            # Intermediate stage: wait for the explicit user confirmation.
            if scan.status in (Scan.Status.COMPLETED, Scan.Status.PARTIAL):
                journey.state = JourneyState.AWAITING_CONFIRMATION
                journey.expires_at = timezone.now() + timedelta(
                    hours=cls.journey_ttl_hours()
                )
            else:
                journey.state = JourneyState.FAILED
                journey.expires_at = None
        else:
            # Final stage: completed only when every result is complete.
            journey.expires_at = None
            if scan.status == Scan.Status.COMPLETED:
                journey.state = JourneyState.COMPLETED
            elif scan.status == Scan.Status.PARTIAL:
                journey.state = JourneyState.PARTIAL
            else:
                journey.state = JourneyState.FAILED

        journey.save(update_fields=["state", "expires_at", "updated_at"])

        logger.info(
            "journey_stage_completed journey_id=%s stage=%s scan_id=%s "
            "scan_status=%s previous_state=%s new_state=%s expires_at=%s",
            journey.pk,
            scan.journey_stage,
            scan_id,
            scan.status,
            previous_state,
            journey.state,
            journey.expires_at.isoformat() if journey.expires_at else None,
        )
        return journey

    # ------------------------------------------------------------------
    # Explicit advancement
    # ------------------------------------------------------------------

    @classmethod
    @transaction.atomic
    def advance_journey(cls, journey_id: Any, requested_by: Any) -> Any:
        """Confirm the next stage and publish its child scan.

        The website lock serialises this call with journey creation and with a
        concurrent ``advance`` for the same site.  `A classic scan in progress
        is a conflict, never a reason to fail the journey: the journey stays
        ``awaiting_confirmation`` and the user can retry once it ends.

        Raises:
            PermissionError: the user may not write on this website.
            JourneyStateError: the journey is not awaiting confirmation (or no
                stage remains).
            JourneyExpiredError: the confirmation window is over.
            JourneyConflictError: a classic scan is currently active.
        """
        from scans.models import JourneyState, Scan, ScanJourney
        from scanners.features import advanced_security_enabled
        from websites.models import Website

        website_id = (
            ScanJourney.objects.filter(pk=journey_id)
            .values_list("website_id", flat=True)
            .first()
        )
        if website_id is None:
            raise JourneyStateError(f"Parcours {journey_id} introuvable")

        # Constant lock order: Website first, Journey second.
        website = Website.objects.select_for_update().get(pk=website_id)
        journey = ScanJourney.objects.select_for_update().get(pk=journey_id)

        check_write_permission(requested_by, website)

        if journey.state != JourneyState.AWAITING_CONFIRMATION:
            raise JourneyStateError(
                f"Parcours {journey.pk} en état {journey.state} : "
                "aucun palier à confirmer"
            )

        now = timezone.now()
        if journey.expires_at is not None and journey.expires_at <= now:
            raise JourneyExpiredError(
                f"Parcours {journey.pk} expiré depuis {journey.expires_at.isoformat()}"
            )

        next_stage = journey.current_stage + 1
        if next_stage > journey.total_stages:
            raise JourneyStateError(
                f"Parcours {journey.pk} : aucun palier après {journey.current_stage}"
            )

        # Monitoring must keep working while a journey waits.  If a classic
        # scan slipped in, advancing now would run two scans on one site.
        active_classic_scan = (
            Scan.objects.filter(
                website=website,
                journey__isnull=True,
                status__in=_ACTIVE_SCAN_STATES,
            )
            .order_by("-created_at")
            .first()
        )
        if active_classic_scan is not None:
            raise JourneyConflictError(
                "Un scan classique est en cours sur ce site "
                f"(scan {active_classic_scan.id}, "
                f"statut {active_classic_scan.status})"
            )

        # Stage 2 relies on Nuclei, which is opt-in.  Running the stage without
        # it would report a coverage the journey never had: fail explicitly
        # instead of producing a false COMPLETED.
        if next_stage == 2 and not advanced_security_enabled():
            journey.state = JourneyState.FAILED
            journey.expires_at = None
            journey.save(update_fields=["state", "expires_at", "updated_at"])
            logger.error(
                "journey_stage_unavailable journey_id=%s stage=2 "
                "reason=advanced_security_disabled",
                journey.pk,
            )
            return journey

        journey.state = JourneyState.RUNNING
        journey.current_stage = next_stage
        journey.expires_at = None
        journey.save(
            update_fields=["state", "current_stage", "expires_at", "updated_at"]
        )

        scan = cls._create_stage_scan(
            journey,
            stage=next_stage,
            # Option A: a journey is one quota unit, charged on stage 1.
            quota_charged=False,
            trigger_source="manual",
        )

        cls._publish_stage(scan)

        logger.info(
            "journey_advanced journey_id=%s stage=%s scan_id=%s",
            journey.pk,
            next_stage,
            scan.pk,
        )
        return journey

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    @classmethod
    @transaction.atomic
    def cancel_journey(cls, journey_id: Any, requested_by: Any) -> Any:
        """Cancel a running or waiting journey and its active child scan.

        The quota is **not** refunded: stage 1 was already counted when the
        journey was admitted.  A child scan already in a terminal state is left
        untouched.
        """
        from scans.models import JourneyState, Scan, ScanJourney

        journey = ScanJourney.objects.select_for_update().get(pk=journey_id)
        check_write_permission(requested_by, journey.website)

        if journey.state not in (
            JourneyState.RUNNING,
            JourneyState.AWAITING_CONFIRMATION,
        ):
            raise JourneyStateError(
                f"Parcours {journey.pk} en état {journey.state} : annulation impossible"
            )

        active_scans = Scan.objects.select_for_update().filter(
            journey=journey,
            status__in=_ACTIVE_SCAN_STATES,
        )
        cancelled: list[int] = []
        for scan in active_scans:
            scan.transition_to(Scan.Status.CANCELLED)
            cancelled.append(scan.pk)

        previous_state = journey.state
        journey.state = JourneyState.CANCELLED
        journey.expires_at = None
        journey.save(update_fields=["state", "expires_at", "updated_at"])

        logger.info(
            "journey_cancelled journey_id=%s previous_state=%s scans=%s",
            journey.pk,
            previous_state,
            cancelled,
        )
        return journey

    # ------------------------------------------------------------------
    # Quota
    # ------------------------------------------------------------------

    @classmethod
    def check_and_reserve_quota(cls, organization: Any) -> bool:
        """Check the monthly quota under an organization row lock.

        The lock is held by the caller's transaction (``create_journey`` is
        already atomic), so the check and the creation of the charged scan form
        one indivisible admission step.  There is no separate increment: the
        charged ``Scan`` row is the counter.

        Returns True when the operation may proceed.  When the organization has
        no billing owner or no plan, no ceiling applies (existing behaviour of
        ``subscriptions.services.quotas``).
        """
        from organizations.models import Organization
        from subscriptions.services.quotas import (
            get_effective_plan_for_organization,
            scans_used_this_month,
        )

        if organization is None:
            return True

        locked = Organization.objects.select_for_update().get(pk=organization.pk)
        plan = get_effective_plan_for_organization(locked)
        if plan is None:
            return True

        used = scans_used_this_month(organization=locked)
        limit = plan.max_scans_per_month
        if used >= limit:
            raise QuotaExceededError(f"Quota dépassé : {used}/{limit}")

        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _create_stage_scan(
        cls,
        journey: Any,
        *,
        stage: int,
        quota_charged: bool,
        trigger_source: str,
    ) -> Any:
        """Create the queued child scan for *stage*.

        ``Scan`` has no ``requested_by`` column; the journey already carries
        the requesting user, and the child only needs its trigger source.
        """
        from scans.models import Scan

        trigger = {
            "monitoring": Scan.Trigger.MONITORING,
            "onboarding": Scan.Trigger.ONBOARDING,
            "public": Scan.Trigger.PUBLIC,
        }.get(trigger_source, Scan.Trigger.MANUAL)

        return Scan.objects.create(
            website=journey.website,
            scan_type=Scan.ScanType.SECURITY,
            trigger=trigger,
            status=Scan.Status.QUEUED,
            journey=journey,
            journey_stage=stage,
            quota_charged=quota_charged,
        )

    @classmethod
    def _publish_stage(cls, scan: Any) -> None:
        """Queue the existing scan task only after the transaction commits."""
        from scans.tasks import run_authenticated_scan

        scan_id = scan.pk

        def _dispatch() -> None:
            try:
                run_authenticated_scan.delay(scan_id)
            except Exception:
                # A broker outage must not roll back the journey: the scan is
                # stored QUEUED and the reaper (or a manual retry) will surface
                # it.  This mirrors the tolerance of the classic paths.
                logger.exception(
                    "journey_stage_dispatch_failed scan_id=%s — the scan row "
                    "is committed and remains queued",
                    scan_id,
                )

        transaction.on_commit(_dispatch)

    @staticmethod
    def journey_ttl_hours() -> int:
        """Configured confirmation window, with a safe minimum of one hour."""
        try:
            return max(1, int(getattr(settings, "SCAN_JOURNEY_TTL_HOURS", 24)))
        except (TypeError, ValueError):
            return 24


__all__ = ("JourneyService", "check_write_permission")
