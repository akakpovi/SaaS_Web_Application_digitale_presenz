import logging

from django.core.cache import cache
from django.db import connection
from django.db.utils import DatabaseError
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """Readiness check for the API and its required backing services."""

    authentication_classes: list[object] = []
    permission_classes: list[object] = []

    @extend_schema(
        responses={
            200: OpenApiResponse(description="All dependencies are reachable."),
            503: OpenApiResponse(description="One or more dependencies are unavailable."),
        },
        tags=["system"],
    )
    def get(self, request: object) -> Response:
        dependencies = {"database": self._database_ready(), "redis": self._cache_ready()}
        is_ready = all(dependencies.values())
        if not is_ready:
            logger.error("health_check_failed", extra={"dependencies": dependencies})

        return Response(
            {"status": "ok" if is_ready else "unavailable", "service": "presence-api", "dependencies": dependencies},
            status=status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    @staticmethod
    def _database_ready() -> bool:
        try:
            connection.ensure_connection()
        except DatabaseError:
            return False
        return True

    @staticmethod
    def _cache_ready() -> bool:
        try:
            return bool(cache.set("healthcheck", "ok", timeout=5) and cache.get("healthcheck") == "ok")
        except Exception:  # Cache backend failures must return 503, not leak details.
            return False
