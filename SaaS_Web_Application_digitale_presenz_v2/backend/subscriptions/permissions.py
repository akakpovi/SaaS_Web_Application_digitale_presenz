"""Permissions liées à l'offre commerciale."""

from rest_framework.permissions import BasePermission

from subscriptions.services.quotas import get_effective_plan


class HasAPIAccess(BasePermission):
    """Autorise uniquement les offres dont ``Plan.can_use_api`` est vrai."""

    message = "API access requires a Pro plan or higher."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        plan = get_effective_plan(user)
        return plan is None or bool(plan.can_use_api)
