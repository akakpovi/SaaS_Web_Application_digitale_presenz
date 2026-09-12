from rest_framework.permissions import BasePermission


class IsEmailVerified(BasePermission):
    """Optional permission for future actions that require a verified email."""

    message = "Verify your email address before performing this action."

    def has_permission(self, request: object, view: object) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_email_verified)
