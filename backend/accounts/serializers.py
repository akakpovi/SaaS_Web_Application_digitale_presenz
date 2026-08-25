"""Serializers for the accounts app."""

from typing import Any

from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from .models import User


class UserSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ("id", "email", "full_name", "is_email_verified", "date_joined", "updated_at")
        read_only_fields = fields


class RegistrationSerializer(serializers.ModelSerializer[User]):
    password = serializers.CharField(write_only=True, min_length=12)

    class Meta:
        model = User
        fields = ("email", "full_name", "password")
        extra_kwargs = {"full_name": {"required": False}}

    def validate_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value

    def create(self, validated_data: dict[str, Any]) -> User:
        return User.objects.create_user(**validated_data)


class PresenceTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds a ``user`` object to the token pair response."""

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class GoogleOAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=12)

    def validate_new_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value

    def save(self, **kwargs: Any) -> User:
        uid = force_str(urlsafe_base64_decode(self.validated_data["uidb64"]))
        user = User.objects.get(pk=uid)
        if not default_token_generator.check_token(user, self.validated_data["token"]):
            raise serializers.ValidationError({"token": "Invalid or expired reset token."})
        user.set_password(self.validated_data["new_password"])
        user.save()
        # Invalidate all existing refresh tokens after password change.
        for token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=token)
        return user


class EmailVerificationSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()

    def save(self, **kwargs: Any) -> User:
        uid = force_str(urlsafe_base64_decode(self.validated_data["uidb64"]))
        user = User.objects.get(pk=uid)
        if not default_token_generator.check_token(user, self.validated_data["token"]):
            raise serializers.ValidationError({"token": "Invalid or expired verification token."})
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        return user
