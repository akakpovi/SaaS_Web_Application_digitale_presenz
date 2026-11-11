import logging

from django.contrib.auth.tokens import default_token_generator
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .providers.google import GoogleOAuthUnavailable
from .serializers import (
    AccountDeletionSerializer,
    EmailVerificationSerializer,
    GoogleOAuthSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PresenceTokenObtainPairSerializer,
    ProfileSerializer,
    RegistrationSerializer,
    UserSerializer,
)
from .services import (
    collect_user_data,
    delete_user_account,
    send_password_reset_email,
    send_verification_email,
)

logger = logging.getLogger(__name__)


class RegistrationView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=RegistrationSerializer,
        responses={201: UserSerializer},
        tags=["authentication"],
    )
    def post(self, request: object) -> Response:
        serializer = RegistrationSerializer(data=getattr(request, "data", {}))
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_verification_email(user)
        logger.info("user_registered", extra={"user_id": user.pk})
        return Response(
            {
                "user": UserSerializer(user).data,
                "detail": "Account created. Check your email to verify it.",
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=PresenceTokenObtainPairSerializer,
        responses={200: OpenApiResponse(description="JWT token pair.")},
        tags=["authentication"],
    )
    def post(self, request: object) -> Response:
        serializer = PresenceTokenObtainPairSerializer(
            data=getattr(request, "data", {})
        )
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=TokenRefreshSerializer,
        responses={200: OpenApiResponse(description="Refreshed JWT token pair.")},
        tags=["authentication"],
    )
    def post(self, request: object) -> Response:
        serializer = TokenRefreshSerializer(data=getattr(request, "data", {}))
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, User.DoesNotExist) as exc:
            # A still-valid refresh JWT can outlive its account (GDPR erasure,
            # admin deletion). SimpleJWT then raises User.DoesNotExist from
            # ``validate()``; without this catch the API answers 500 instead of
            # telling the client to drop its session.
            raise InvalidToken("This refresh token is invalid or expired.") from exc
        return Response(serializer.validated_data)


class LogoutView(APIView):
    @extend_schema(
        request=LogoutSerializer,
        responses={204: OpenApiResponse(description="Refresh token invalidated.")},
        tags=["authentication"],
    )
    def post(self, request: object) -> Response:
        serializer = LogoutSerializer(data=getattr(request, "data", {}))
        serializer.is_valid(raise_exception=True)
        refresh_token = serializer.validated_data["refresh"]
        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError:
            raise ValidationError({"refresh": "This token is invalid or expired."})
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    """``GET`` the current account, ``DELETE`` it (GDPR Art. 17 erasure).

    Deletion is confirmed with the account password so a stolen access token is
    not enough to destroy an account.  The response carries an audit summary of
    the cascaded rows; the account, its websites, scans, findings, alerts and
    notification channels are gone by the time it is returned.
    """

    @extend_schema(responses={200: UserSerializer}, tags=["authentication"])
    def get(self, request: object) -> Response:
        return Response(UserSerializer(getattr(request, "user")).data)

    @extend_schema(
        request=AccountDeletionSerializer,
        responses={
            200: OpenApiResponse(description="Account and all attached data erased."),
            400: OpenApiResponse(
                description="Password confirmation missing or incorrect."
            ),
        },
        tags=["authentication"],
    )
    def delete(self, request: object) -> Response:
        user: User = getattr(request, "user")
        serializer = AccountDeletionSerializer(
            data=getattr(request, "data", {}) or {}, context={"user": user}
        )
        serializer.is_valid(raise_exception=True)

        # The traffic middleware runs *after* this view and reads the raw
        # ``HttpRequest``: flag it there (DRF's ``Request`` proxies reads, not
        # writes) so it never attributes traffic to the erased account.
        http_request = getattr(request, "_request", request)
        setattr(http_request, "skip_traffic_log", True)

        summary = delete_user_account(user)
        return Response(
            {
                "detail": "Account and all attached data have been deleted.",
                **summary,
            },
            status=status.HTTP_200_OK,
        )


class DataExportView(APIView):
    """``GET /api/v1/auth/export/`` — full data portability dump (GDPR Art. 15/20).

    Returns one JSON document containing the account record and every
    user-owned dataset (websites, scans, check results, scanner runs, findings,
    alerts, monitoring, reports, reviews, SEO and social data).
    """

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description="Machine-readable export of all account data."
            )
        },
        tags=["authentication"],
    )
    def get(self, request: object) -> Response:
        user: User = getattr(request, "user")
        response = Response(collect_user_data(user), status=status.HTTP_200_OK)
        # The payload is personal data: never cache it in a shared proxy.
        response["Cache-Control"] = "private, no-store"
        response["Content-Disposition"] = (
            f'attachment; filename="presence-export-{user.pk}.json"'
        )
        return response


class ProfileView(APIView):
    """``GET`` / ``PATCH`` the signed-in user's preferences.

    Business information and display language used to be hard-coded in the
    settings screen with no persistence; both are now stored on the account
    and scoped to the authenticated user.
    """

    @extend_schema(responses={200: ProfileSerializer}, tags=["authentication"])
    def get(self, request: object) -> Response:
        return Response(ProfileSerializer(getattr(request, "user")).data)

    @extend_schema(
        request=ProfileSerializer,
        responses={200: ProfileSerializer},
        tags=["authentication"],
    )
    def patch(self, request: object) -> Response:
        user: User = getattr(request, "user")
        serializer = ProfileSerializer(
            user, data=getattr(request, "data", {}), partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={202: OpenApiResponse(description="Reset request accepted.")},
        tags=["authentication"],
    )
    def post(self, request: object) -> Response:
        serializer = PasswordResetRequestSerializer(data=getattr(request, "data", {}))
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            send_password_reset_email(user)
        # Deliberately identical response for existing and unknown addresses.
        return Response(
            {"detail": "If that account exists, a reset link has been sent."},
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={200: OpenApiResponse(description="Password changed.")},
        tags=["authentication"],
    )
    def post(self, request: object) -> Response:
        serializer = PasswordResetConfirmSerializer(data=getattr(request, "data", {}))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password reset successful."})


class EmailVerificationView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=EmailVerificationSerializer,
        responses={200: UserSerializer},
        tags=["authentication"],
    )
    def post(self, request: object) -> Response:
        serializer = EmailVerificationSerializer(data=getattr(request, "data", {}))
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"user": UserSerializer(user).data, "detail": "Email address verified."}
        )


class EmailVerificationResendView(APIView):
    @extend_schema(
        request=None,
        responses={
            202: OpenApiResponse(description="Verification email request accepted.")
        },
        tags=["authentication"],
    )
    def post(self, request: object) -> Response:
        user: User = getattr(request, "user")
        if not user.is_email_verified:
            send_verification_email(user)
        return Response(
            {"detail": "If needed, a verification email has been sent."},
            status=status.HTTP_202_ACCEPTED,
        )


class GoogleOAuthView(APIView):
    """Stable API boundary; a provider implementation is intentionally not configured yet."""

    permission_classes = [AllowAny]

    @extend_schema(
        request=GoogleOAuthSerializer,
        responses={501: OpenApiResponse(description="Google OAuth is not configured.")},
        tags=["authentication"],
    )
    def post(self, request: object) -> Response:
        raise GoogleOAuthUnavailable("Google OAuth is not configured.")
