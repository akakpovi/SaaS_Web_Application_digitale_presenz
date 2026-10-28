from django.urls import path

from .views import (
    CurrentUserView,
    DataExportView,
    EmailVerificationResendView,
    EmailVerificationView,
    GoogleOAuthView,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegistrationView,
    TokenRefreshView,
)

urlpatterns = [
    path("register/", RegistrationView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", CurrentUserView.as_view(), name="auth-me"),
    path("export/", DataExportView.as_view(), name="auth-export"),
    path("password/reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("password/reset/confirm/", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("email/verify/", EmailVerificationView.as_view(), name="auth-email-verify"),
    path("email/verify/resend/", EmailVerificationResendView.as_view(), name="auth-email-verify-resend"),
    path("oauth/google/", GoogleOAuthView.as_view(), name="auth-google-oauth"),
]
