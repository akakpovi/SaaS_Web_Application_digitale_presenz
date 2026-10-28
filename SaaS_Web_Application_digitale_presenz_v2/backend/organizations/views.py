"""Team-management endpoints for organizations.

All routes resolve the organization from the URL and the caller's membership,
never from a client-supplied role.  Non-members receive 404 so tenant ids
cannot be probed; members without a sufficient role receive 403.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User

from .access import MANAGE_MEMBER_ROLES, role_for_organization
from .models import Membership, Organization, OrganizationInvitation
from .serializers import (
    OrganizationInvitationSerializer,
    OrganizationMemberCreateSerializer,
    OrganizationMemberSerializer,
    OrganizationMemberUpdateSerializer,
    OrganizationSerializer,
)
from .services import (
    InvitationAlreadyUsed,
    InvitationEmailMismatch,
    InvitationExpired,
    InvitationNotFound,
    accept_invitation,
    invite_accept_url,
    issue_invitation,
    normalize_email,
    send_invitation_email,
)


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The resource already exists."
    default_code = "conflict"


class Gone(APIException):
    status_code = status.HTTP_410_GONE
    default_detail = "The resource is no longer available."
    default_code = "gone"


def _organization_and_role(request: Request, organization_id) -> tuple[Organization, str]:
    organization = (
        Organization.objects.select_related("billing_owner")
        .filter(pk=organization_id)
        .first()
    )
    if organization is None:
        raise NotFound("Organization not found.")
    role = role_for_organization(request.user, organization)
    if role is None:
        raise NotFound("Organization not found.")
    return organization, role


def _require_manager(role: str) -> None:
    if role not in MANAGE_MEMBER_ROLES:
        raise PermissionDenied(
            "Your organization role does not allow managing team members."
        )


def _member_queryset(organization: Organization):
    return (
        Membership.objects.filter(organization=organization)
        .select_related("user", "organization", "organization__billing_owner")
        .order_by("created_at")
    )


def _member_or_404(organization: Organization, pk) -> Membership:
    membership = (
        _member_queryset(organization)
        .filter(pk=pk)
        .first()
    )
    if membership is None:
        raise NotFound("Member not found.")
    return membership


def _assert_target_is_mutable(actor_role: str, membership: Membership) -> None:
    """Prevent privilege escalation and accidental owner removal."""
    if membership.role == Membership.Role.OWNER:
        raise PermissionDenied("The organization owner cannot be changed or removed.")
    if membership.user_id == membership.organization.billing_owner_id:
        raise PermissionDenied("The billing owner cannot be changed or removed.")
    if membership.role == Membership.Role.ADMIN and actor_role != Membership.Role.OWNER:
        raise PermissionDenied("Only the owner can change another administrator.")


class OrganizationListAPIView(generics.ListAPIView):
    """GET /api/v1/organizations/ — tenants available to the caller."""

    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        user = self.request.user
        return (
            Organization.objects.filter(
                Q(billing_owner=user) | Q(memberships__user=user)
            )
            .select_related("billing_owner")
            .distinct()
            .order_by("name")
        )


class OrganizationMemberListCreateView(APIView):
    """GET/POST /api/v1/organizations/<id>/members/."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, organization_id) -> Response:
        organization, _role = _organization_and_role(request, organization_id)
        members = _member_queryset(organization)
        return Response(OrganizationMemberSerializer(members, many=True).data)

    def post(self, request: Request, organization_id) -> Response:
        organization, role = _organization_and_role(request, organization_id)
        _require_manager(role)

        serializer = OrganizationMemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        requested_role = serializer.validated_data["role"]

        if requested_role == Membership.Role.ADMIN and role != Membership.Role.OWNER:
            raise PermissionDenied("Only the owner can add an administrator.")

        target = User.objects.filter(email__iexact=normalize_email(email)).first()
        if target is not None:
            if target.pk == organization.billing_owner_id:
                raise Conflict("This user is the organization owner.")
            if Membership.objects.filter(
                organization=organization,
                user=target,
            ).exists():
                raise Conflict("This user is already a member of the organization.")

        from subscriptions.services.quotas import assert_can_add_team_member

        assert_can_add_team_member(organization)

        if target is None:
            invitation, token = issue_invitation(
                organization,
                email=email,
                role=requested_role,
                invited_by=request.user,
            )
            email_sent = send_invitation_email(invitation, token)
            payload = OrganizationInvitationSerializer(invitation).data
            return Response(
                {
                    "status": "invited",
                    "email": invitation.email,
                    "email_sent": email_sent,
                    "accept_url": invite_accept_url(token),
                    "invitation": payload,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        try:
            with transaction.atomic():
                membership = Membership.objects.create(
                    organization=organization,
                    user=target,
                    role=requested_role,
                )
                now = timezone.now()
                OrganizationInvitation.objects.filter(
                    organization=organization,
                    email__iexact=normalize_email(target.email),
                    status=OrganizationInvitation.Status.PENDING,
                ).update(
                    status=OrganizationInvitation.Status.ACCEPTED,
                    accepted_at=now,
                    updated_at=now,
                )
        except IntegrityError:
            raise Conflict("This user is already a member of the organization.")

        return Response(
            OrganizationMemberSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationMemberDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/organizations/<id>/members/<pk>/."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, organization_id, pk) -> Response:
        organization, _role = _organization_and_role(request, organization_id)
        membership = _member_or_404(organization, pk)
        return Response(OrganizationMemberSerializer(membership).data)

    def patch(self, request: Request, organization_id, pk) -> Response:
        organization, actor_role = _organization_and_role(request, organization_id)
        _require_manager(actor_role)
        membership = _member_or_404(organization, pk)
        _assert_target_is_mutable(actor_role, membership)

        serializer = OrganizationMemberUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_role = serializer.validated_data["role"]
        if new_role == Membership.Role.ADMIN and actor_role != Membership.Role.OWNER:
            raise PermissionDenied("Only the owner can promote an administrator.")

        membership.role = new_role
        membership.save(update_fields=["role", "updated_at"])
        return Response(OrganizationMemberSerializer(membership).data)

    def delete(self, request: Request, organization_id, pk) -> Response:
        organization, actor_role = _organization_and_role(request, organization_id)
        _require_manager(actor_role)
        membership = _member_or_404(organization, pk)
        _assert_target_is_mutable(actor_role, membership)
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationInvitationListView(APIView):
    """GET /api/v1/organizations/<id>/invitations/."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, organization_id) -> Response:
        organization, role = _organization_and_role(request, organization_id)
        _require_manager(role)
        qs = (
            OrganizationInvitation.objects.filter(organization=organization)
            .select_related("invited_by", "organization")
            .order_by("-created_at")
        )
        requested_status = request.query_params.get("status")
        valid_statuses = {choice for choice, _ in OrganizationInvitation.Status.choices}
        if requested_status in valid_statuses:
            qs = qs.filter(status=requested_status)
        else:
            qs = qs.filter(status=OrganizationInvitation.Status.PENDING)
        return Response(OrganizationInvitationSerializer(qs, many=True).data)


class OrganizationInvitationDetailView(APIView):
    """DELETE /api/v1/organizations/<id>/invitations/<pk>/ — revoke."""

    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, organization_id, pk) -> Response:
        organization, role = _organization_and_role(request, organization_id)
        _require_manager(role)
        invitation = (
            OrganizationInvitation.objects.filter(
                organization=organization,
                pk=pk,
            ).first()
        )
        if invitation is None or invitation.status != OrganizationInvitation.Status.PENDING:
            raise NotFound("Invitation not found.")
        invitation.status = OrganizationInvitation.Status.REVOKED
        invitation.save(update_fields=["status", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitationAcceptView(APIView):
    """POST /api/v1/organizations/invitations/<token>/accept/."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, token: str) -> Response:
        try:
            membership = accept_invitation(token, request.user)
        except InvitationNotFound:
            raise NotFound("Invitation not found.")
        except InvitationExpired:
            raise Gone(
                detail="This invitation has expired.",
                code="invitation_expired",
            )
        except InvitationAlreadyUsed:
            raise Conflict("This invitation has already been used.")
        except InvitationEmailMismatch:
            raise PermissionDenied(
                "This invitation was issued for a different e-mail address."
            )
        return Response(
            OrganizationMemberSerializer(membership).data,
            status=status.HTTP_200_OK,
        )
