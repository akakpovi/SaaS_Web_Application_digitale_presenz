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
    EmailVerificationSerializer,
    GoogleOAuthSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PresenceTokenObtainPairSerializer,
    RegistrationSerializer,
    UserSerializer,
)
from .services import send_password_reset_email, send_verification_email

logger = logging.getLogger(__name__)


class RegistrationView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=RegistrationSerializer, responses={201: UserSerializer}, tags=["authentication"])
    def post(self, request: object) -> Response:
        serializer = RegistrationSerializer(data=getattr(request, "data", {}))
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_verification_email(user)
        logger.info("user_registered", extra={"user_id": user.pk})
        return Response({"user": UserSerializer(user).data, "detail": "Account created. Check your email to verify it."}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=PresenceTokenObtainPairSerializer, responses={200: OpenApiResponse(description="JWT token pair.")}, tags=["authentication"])
    def post(self, request: object) -> Response:
        serializer = PresenceTokenObtainPairSerializer(data=getattr(request, "data", {}))
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=TokenRefreshSerializer, responses={200: OpenApiResponse(description="Refreshed JWT token pair.")}, tags=["authentication"])
    def post(self, request: object) -> Response:
        serializer = TokenRefreshSerializer(data=getattr(request, "data", {}))
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken("This refresh token is invalid or expired.") from exc
        return Response(serializer.validated_data)


class LogoutView(APIView):
    @extend_schema(request=LogoutSerializer, responses={204: OpenApiResponse(description="Refresh token invalidated.")}, tags=["authentication"])
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
    @extend_schema(responses={200: UserSerializer}, tags=["authentication"])
    def get(self, request: object) -> Response:
        return Response(UserSerializer(getattr(request, "user")).data)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=PasswordResetRequestSerializer, responses={202: OpenApiResponse(description="Reset request accepted.")}, tags=["authentication"])
    def post(self, request: object) -> Response:
        serializer = PasswordResetRequestSerializer(data=getattr(request, "data", {}))
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            send_password_reset_email(user)
        # Deliberately identical response for existing and unknown addresses.
        return Response({"detail": "If that account exists, a reset link has been sent."}, status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=PasswordResetConfirmSerializer, responses={200: OpenApiResponse(description="Password changed.")}, tags=["authentication"])
    def post(self, request: object) -> Response:
        serializer = PasswordResetConfirmSerializer(data=getattr(request, "data", {}))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password reset successful."})


class EmailVerificationView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=EmailVerificationSerializer, responses={200: UserSerializer}, tags=["authentication"])
    def post(self, request: object) -> Response:
        serializer = EmailVerificationSerializer(data=getattr(request, "data", {}))
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({"user": UserSerializer(user).data, "detail": "Email address verified."})


class EmailVerificationResendView(APIView):
    @extend_schema(request=None, responses={202: OpenApiResponse(description="Verification email request accepted.")}, tags=["authentication"])
    def post(self, request: object) -> Response:
        user: User = getattr(request, "user")
        if not user.is_email_verified:
            send_verification_email(user)
        return Response({"detail": "If needed, a verification email has been sent."}, status=status.HTTP_202_ACCEPTED)


class GoogleOAuthView(APIView):
    """Stable API boundary; a provider implementation is intentionally not configured yet."""

    permission_classes = [AllowAny]

    @extend_schema(request=GoogleOAuthSerializer, responses={501: OpenApiResponse(description="Google OAuth is not configured.")}, tags=["authentication"])
    def post(self, request: object) -> Response:
        raise GoogleOAuthUnavailable("Google OAuth is not configured.")
