"""Gestion des clés d'API personnelles (offres ``can_use_api``)."""

from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from subscriptions.models import ApiKey
from subscriptions.permissions import HasAPIAccess


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = ["id", "name", "prefix", "created_at", "last_used_at", "revoked_at"]
        read_only_fields = fields


class ApiKeyListCreateView(APIView):
    """GET/POST /api/v1/api-keys/"""

    permission_classes = [IsAuthenticated, HasAPIAccess]

    def get(self, request) -> Response:
        keys = ApiKey.objects.filter(
            user=request.user, revoked_at__isnull=True
        )
        return Response(ApiKeySerializer(keys, many=True).data)

    def post(self, request) -> Response:
        name = str(request.data.get("name", "")).strip() or "Default key"
        if len(name) > 100:
            return Response(
                {"detail": "Key name is too long (100 characters max)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        key, raw_key = ApiKey.issue(request.user, name)
        data = ApiKeySerializer(key).data
        # The plaintext key is returned exactly once.
        data["api_key"] = raw_key
        return Response(data, status=status.HTTP_201_CREATED)


class ApiKeyRevokeView(APIView):
    """DELETE /api/v1/api-keys/<uuid>/"""

    permission_classes = [IsAuthenticated, HasAPIAccess]

    def delete(self, request, pk) -> Response:
        key = ApiKey.objects.filter(
            pk=pk, user=request.user, revoked_at__isnull=True
        ).first()
        if key is None:
            return Response(
                {"detail": "API key not found."}, status=status.HTTP_404_NOT_FOUND
            )
        key.revoked_at = timezone.now()
        key.save(update_fields=["revoked_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
