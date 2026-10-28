"""DRF permissions for the organization-scoped website API."""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

from organizations.access import DELETE_ROLES, WRITE_ROLES, role_for_website


class WebsiteRolePermission(BasePermission):
    """Apply the Owner/Admin/Analyst/Viewer matrix to website actions.

    Reads are available to every member role.  Mutations require Analyst or
    above; deleting a tenant website is reserved to Admin and Owner so an
    analyst cannot remove the whole monitoring target.
    """

    message = "Your organization role does not allow this action."

    def has_object_permission(self, request, view, obj) -> bool:
        role = role_for_website(request.user, obj)
        if role is None:
            return False
        if request.method in SAFE_METHODS:
            return True
        if getattr(view, "action", None) == "destroy":
            return role in DELETE_ROLES
        return role in WRITE_ROLES
