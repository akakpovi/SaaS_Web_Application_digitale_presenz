"""Serializers for organization, membership and invitation APIs."""

from __future__ import annotations

from rest_framework import serializers

from accounts.models import User

from .access import role_for_organization
from .models import Membership, Organization, OrganizationInvitation
from .services import normalize_email


class OrganizationSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    pending_invitations = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "is_personal",
            "role",
            "member_count",
            "pending_invitations",
            "created_at",
        ]
        read_only_fields = fields

    def get_role(self, obj: Organization) -> str | None:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return role_for_organization(user, obj)

    def get_member_count(self, obj: Organization) -> int:
        return obj.memberships.count()

    def get_pending_invitations(self, obj: Organization) -> int:
        return obj.invitations.filter(
            status=OrganizationInvitation.Status.PENDING
        ).count()


class OrganizationMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    is_owner = serializers.SerializerMethodField()
    joined_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id",
            "user_id",
            "email",
            "full_name",
            "role",
            "role_display",
            "is_owner",
            "joined_at",
        ]
        read_only_fields = fields

    def get_is_owner(self, obj: Membership) -> bool:
        return obj.user_id == obj.organization.billing_owner_id


class OrganizationMemberCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=OrganizationInvitation.ASSIGNABLE_ROLE_CHOICES,
        default=Membership.Role.VIEWER,
    )

    def validate_email(self, value: str) -> str:
        return User.objects.normalize_email(normalize_email(value))


class OrganizationMemberUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=OrganizationInvitation.ASSIGNABLE_ROLE_CHOICES,
    )


class OrganizationInvitationSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    invited_by_email = serializers.EmailField(
        source="invited_by.email",
        read_only=True,
        allow_null=True,
    )
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = OrganizationInvitation
        fields = [
            "id",
            "email",
            "role",
            "role_display",
            "status",
            "invited_by_email",
            "expires_at",
            "is_expired",
            "accepted_at",
            "created_at",
        ]
        read_only_fields = fields
