"""Organization helpers shared by websites, scans and team management."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from .access import MANAGE_MEMBER_ROLES, role_for_organization
from .models import (
    Membership,
    Organization,
    OrganizationInvitation,
    invitation_default_expiry,
)

INVITATION_TTL = timedelta(days=7)


class InvitationError(Exception):
    """Base class for invitation failures mapped to API responses."""


class InvitationNotFound(InvitationError):
    pass


class InvitationExpired(InvitationError):
    pass


class InvitationAlreadyUsed(InvitationError):
    pass


class InvitationEmailMismatch(InvitationError):
    pass


def _personal_organization_name(user: Any) -> str:
    business_name = (getattr(user, "business_name", "") or "").strip()
    if business_name:
        return business_name[:150]
    email = (getattr(user, "email", "") or "").strip()
    local_part = email.split("@", 1)[0]
    return (local_part or "Personal")[:150]


def ensure_personal_organization(user: Any) -> Organization:
    """Return the user's personal organization, creating it once if needed.

    The partial unique constraint is the concurrency guard: two workers racing
    to create the same personal organization cannot both commit, and the loser
    re-reads the winner's row.
    """
    existing = (
        Organization.objects.filter(billing_owner=user, is_personal=True)
        .order_by("created_at")
        .first()
    )
    if existing is not None:
        Membership.objects.get_or_create(
            organization=existing,
            user=user,
            defaults={"role": Membership.Role.OWNER},
        )
        return existing

    try:
        with transaction.atomic():
            organization = Organization.objects.create(
                name=_personal_organization_name(user),
                billing_owner=user,
                is_personal=True,
            )
            Membership.objects.create(
                organization=organization,
                user=user,
                role=Membership.Role.OWNER,
            )
            return organization
    except IntegrityError:
        organization = Organization.objects.get(
            billing_owner=user,
            is_personal=True,
        )
        Membership.objects.get_or_create(
            organization=organization,
            user=user,
            defaults={"role": Membership.Role.OWNER},
        )
        return organization


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def invite_email_path(token: str) -> str:
    return f"/accept-invitation?token={token}"


def invite_accept_url(token: str) -> str:
    return f"{settings.FRONTEND_URL}{invite_email_path(token)}"


def send_invitation_email(invitation: OrganizationInvitation, token: str) -> bool:
    """Send the invitation e-mail; return whether the backend accepted it.

    A mail outage must not roll back the invitation, so failures are reported
    to the caller as ``False`` while the pending row remains valid.
    """
    accept_url = invite_accept_url(token)
    subject = f"You have been invited to {invitation.organization.name}"
    message = (
        f"{invitation.invited_by.email if invitation.invited_by else 'An administrator'} "
        f"invited you to join {invitation.organization.name} as "
        f"{invitation.get_role_display()}.\n\n"
        f"Accept the invitation: {accept_url}\n\n"
        f"This invitation expires on {invitation.expires_at:%Y-%m-%d %H:%M} UTC."
    )
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [invitation.email],
            fail_silently=False,
        )
    except Exception:
        return False
    return True


def issue_invitation(
    organization: Organization,
    email: str,
    role: str,
    invited_by: Any,
) -> tuple[OrganizationInvitation, str]:
    """Create or refresh the pending invitation and return its raw token."""
    normalized_email = normalize_email(email)
    if role not in {
        choice for choice, _ in OrganizationInvitation.ASSIGNABLE_ROLE_CHOICES
    }:
        raise ValueError("Invalid invitation role.")

    token = secrets.token_urlsafe(32)
    with transaction.atomic():
        invitation = (
            OrganizationInvitation.objects.select_for_update()
            .filter(
                organization=organization,
                email=normalized_email,
                status=OrganizationInvitation.Status.PENDING,
            )
            .first()
        )
        if invitation is None:
            invitation = OrganizationInvitation(
                organization=organization,
                email=normalized_email,
            )
        invitation.role = role
        invitation.invited_by = invited_by
        invitation.token_hash = _token_digest(token)
        invitation.expires_at = invitation_default_expiry()
        invitation.save()
    return invitation, token


def accept_invitation(token: str, user: Any) -> Membership:
    """Consume *token* for *user*, creating the membership exactly once."""
    if not token:
        raise InvitationNotFound()

    with transaction.atomic():
        invitation = (
            OrganizationInvitation.objects.select_for_update()
            .select_related("organization")
            .filter(token_hash=_token_digest(token))
            .first()
        )
        if (
            invitation is None
            or invitation.status == OrganizationInvitation.Status.REVOKED
        ):
            raise InvitationNotFound()
        if invitation.status == OrganizationInvitation.Status.ACCEPTED:
            existing = Membership.objects.filter(
                organization=invitation.organization,
                user=user,
            ).first()
            if existing is not None:
                return existing
            raise InvitationAlreadyUsed()
        if invitation.status == OrganizationInvitation.Status.EXPIRED:
            raise InvitationExpired()
        if invitation.expires_at <= timezone.now():
            # Record the terminal status and commit it before raising: an
            # exception inside the atomic block would roll the update back.
            invitation.status = OrganizationInvitation.Status.EXPIRED
            invitation.save(update_fields=["status", "updated_at"])
            existing = None
        else:
            if normalize_email(user.email) != normalize_email(invitation.email):
                raise InvitationEmailMismatch()

            existing = Membership.objects.filter(
                organization=invitation.organization,
                user=user,
            ).first()
            if existing is None:
                from subscriptions.services.quotas import assert_can_add_team_member

                assert_can_add_team_member(
                    invitation.organization,
                    include_pending=False,
                )
                existing = Membership.objects.create(
                    organization=invitation.organization,
                    user=user,
                    role=invitation.role,
                )

            invitation.status = OrganizationInvitation.Status.ACCEPTED
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=["status", "accepted_at", "updated_at"])

    if existing is None:
        raise InvitationExpired()
    return existing


def revoke_invitation(invitation: OrganizationInvitation, actor: Any) -> None:
    if role_for_organization(actor, invitation.organization) not in MANAGE_MEMBER_ROLES:
        raise PermissionError("Your organization role does not allow this action.")
    if invitation.status != OrganizationInvitation.Status.PENDING:
        raise InvitationNotFound()
    invitation.status = OrganizationInvitation.Status.REVOKED
    invitation.save(update_fields=["status", "updated_at"])
