"""Organization and role checks for the AI advisory API.

The organization is always derived from the resource (``scan.website``),
never from a client-supplied organization id.  A missing membership is
reported as 404 by the views so the API does not reveal whether a guessed
scan exists in another tenant.
"""

from __future__ import annotations

from typing import Any

from organizations.access import WRITE_ROLES, scan_access_q
from organizations.access import role_for_website as _role_for_website
from scans.models import Scan
from websites.models import Website


def get_scan_for_user(scan_id: Any, user: Any) -> Scan | None:
    """Return *scan_id* only when *user* belongs to its organization/owner."""
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return (
        Scan.objects.select_related("website", "website__organization")
        .filter(scan_access_q(user), pk=scan_id)
        .distinct()
        .first()
    )


def role_for_website(user: Any, website: Website) -> str | None:
    """Return the user's effective role on a website, or ``None``.

    The organization billing owner is always the organization owner.  Team
    members get the role stored in their organization membership.  A viewer
    can read advisory data but cannot accept or dismiss recommendations.
    """
    return _role_for_website(user, website)


def can_manage_recommendations(user: Any, website: Website) -> bool:
    return role_for_website(user, website) in WRITE_ROLES
