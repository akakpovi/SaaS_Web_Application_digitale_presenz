"""Read serializers for connector metadata.

These serializers intentionally omit ``access_token_ciphertext`` and
``refresh_token_ciphertext``.  A future API must use them (or an equally
restrictive projection) rather than ``fields = "__all__"``.
"""

from rest_framework import serializers

from .models import OAuthConnection, OAuthState, SocialAuditEvent


class OAuthConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OAuthConnection
        fields = (
            "id",
            "organization",
            "provider",
            "external_account_id",
            "status",
            "expires_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SocialAuditEventSerializer(serializers.ModelSerializer):
    """Read-only audit projection; contains no token material."""

    class Meta:
        model = SocialAuditEvent
        fields = (
            "id",
            "organization",
            "actor",
            "actor_email",
            "action",
            "provider",
            "external_account_id",
            "connection_id",
            "ip_address",
            "created_at",
        )
        read_only_fields = fields


class OAuthStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OAuthState
        fields = (
            "id",
            "organization",
            "provider",
            "expires_at",
            "created_at",
        )
        read_only_fields = fields
