import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from .models import User

logger = logging.getLogger(__name__)


def blacklist_user_refresh_tokens(user: User) -> None:
    """Invalidate active refresh tokens after a credential reset."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


def send_verification_email(user: User) -> bool:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verify_path = f"/verify-email?uid={uid}&token={token}"
    try:
        send_mail(
            subject="Verify your Presence email address",
            message=f"Verify your email address: {settings.FRONTEND_URL}{verify_path}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("verification_email_delivery_failed", extra={"user_id": user.pk})
        return False
    return True


def send_password_reset_email(user: User) -> bool:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_path = f"/reset-password?uid={uid}&token={token}"
    try:
        send_mail(
            subject="Reset your Presence password",
            message=f"Reset your password: {settings.FRONTEND_URL}{reset_path}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("password_reset_email_delivery_failed", extra={"user_id": user.pk})
        return False
    return True
