import uuid
from typing import Any

from django.core.cache import cache
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    PublicScanRequestSerializer,
    PublicScanStateSerializer,
)
from .tasks import PUBLIC_SCANNERS, run_public_scan


PUBLIC_SCAN_CACHE_TTL = 900


class PublicScanCreateView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "public_scan_create"

    @extend_schema(
        request=PublicScanRequestSerializer,
        responses={
            202: PublicScanStateSerializer,
            400: OpenApiResponse(
                description="Invalid or unsafe domain."
            ),
            429: OpenApiResponse(
                description="Public scan rate limit exceeded."
            ),
        },
        tags=["public"],
    )
    def post(self, request: Request) -> Response:
        serializer = PublicScanRequestSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        domain: str = serializer.validated_data["domain"]
        scan_id = str(uuid.uuid4())

        state: dict[str, Any] = {
            "id": scan_id,
            "scan_id": scan_id,
            "domain": domain,
            "status": "queued",
            "progress": 0,
            "health_score": None,
            "health_status": None,
            "checks": [],
        }

        cache.set(
            f"public_scan:{scan_id}",
            state,
            timeout=PUBLIC_SCAN_CACHE_TTL,
        )

        # The HTTP process only enqueues one orchestration task.
        # It never performs the actual scan.
        run_public_scan.delay(
            domain,
            scan_id,
        )

        return Response(
            {
                **state,
                "poll_url": (
                    f"/api/v1/public/check/{scan_id}/"
                ),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class PublicScanDetailView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "public_scan_poll"

    @extend_schema(
        responses={
            200: PublicScanStateSerializer,
            404: OpenApiResponse(
                description="Scan not found or expired."
            ),
            429: OpenApiResponse(
                description="Polling rate limit exceeded."
            ),
        },
        tags=["public"],
    )
    def get(
        self,
        request: Request,
        scan_id: str,
    ) -> Response:
        state = cache.get(
            f"public_scan:{scan_id}"
        )

        if state is None:
            return Response(
                {
                    "detail":
                        "Scan not found or expired."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if state.get("status") in {
            "queued",
            "processing",
        }:
            completed = sum(
                1
                for scanner_name in PUBLIC_SCANNERS
                if cache.get(
                    f"public_scan:{scan_id}:result:"
                    f"{scanner_name}"
                )
                is not None
            )

            state["progress"] = min(
                int(
                    (
                        completed
                        / len(PUBLIC_SCANNERS)
                    )
                    * 100
                ),
                99,
            )

        serializer = PublicScanStateSerializer(
            state
        )

        return Response(serializer.data)