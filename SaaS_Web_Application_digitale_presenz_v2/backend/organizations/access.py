"""Shared organization access rules for websites, scans and team APIs."""

from __future__ import annotations

from typing import Any

from django.db.models import Q

from .models import Membership, Organization

READ_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.ANALYST,
        Membership.Role.VIEWER,
    }
)
WRITE_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.ANALYST,
    }
)
DELETE_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    }
)
MANAGE_MEMBER_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    }
)
ASSIGNABLE_ROLES = frozenset(
    {
        Membership.Role.ADMIN,
        Membership.Role.ANALYST,
        Membership.Role.VIEWER,
    }
)


def role_for_organization(user: Any, organization: Organization) -> str | None:
    """Return the user's effective role in *organization*, or ``None``."""
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if organization.billing_owner_id == getattr(user, "pk", None):
        return Membership.Role.OWNER
    return (
        Membership.objects.filter(
            organization=organization,
            user=user,
        )
        .values_list("role", flat=True)
        .first()
    )


def role_for_website(user: Any, website: Any) -> str | None:
    """Resolve a website role from its organization, not its creator.

    ``Website.owner`` remains the creator/audit field.  It only grants access
    for legacy organization-less websites; on tenant websites the membership
    (or the organization's billing owner) is authoritative.
    """
    if website.organization_id is not None:
        return role_for_organization(user, website.organization)
    if getattr(website, "owner_id", None) == getattr(user, "pk", None):
        return Membership.Role.OWNER
    return None


def website_access_q(user: Any) -> Q:
    """Q object matching every website the user may read."""
    return (
        Q(organization__billing_owner=user)
        | Q(organization__memberships__user=user)
        | Q(organization__isnull=True, owner=user)
    )


def scan_access_q(user: Any) -> Q:
    """Q object matching every scan the user may read."""
    return (
        Q(website__organization__billing_owner=user)
        | Q(website__organization__memberships__user=user)
        | Q(website__organization__isnull=True, website__owner=user)
    )


def check_result_access_q(user: Any) -> Q:
    """Q object matching every CheckResult the user may read."""
    return (
        Q(scan__website__organization__billing_owner=user)
        | Q(scan__website__organization__memberships__user=user)
        | Q(scan__website__organization__isnull=True, scan__website__owner=user)
    )


def can_read_website(user: Any, website: Any) -> bool:
    return role_for_website(user, website) in READ_ROLES


def can_write_website(user: Any, website: Any) -> bool:
    return role_for_website(user, website) in WRITE_ROLES


def can_delete_website(user: Any, website: Any) -> bool:
    return role_for_website(user, website) in DELETE_ROLES
