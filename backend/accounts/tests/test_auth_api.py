from urllib.parse import parse_qs, urlparse

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class AuthenticationAPITests(APITestCase):
    password = "CorrectHorseBattery1!"

    def register(self, email: str = "maria@example.com") -> dict[str, object]:
        response = self.client.post(
            "/api/v1/auth/register/",
            {"email": email, "full_name": "Maria Schmidt", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def login(self, email: str = "maria@example.com", password: str | None = None) -> dict[str, object]:
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": password or self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def test_registration_creates_custom_user_and_sends_verification(self) -> None:
        payload = self.register()

        user = User.objects.get(email="maria@example.com")
        self.assertEqual(payload["user"]["email"], user.email)
        self.assertFalse(user.is_email_verified)
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("verify-email", mail.outbox[0].body)

    def test_registration_rejects_weak_password_and_duplicate_email(self) -> None:
        weak = self.client.post("/api/v1/auth/register/", {"email": "maria@example.com", "password": "short"}, format="json")
        self.assertEqual(weak.status_code, status.HTTP_400_BAD_REQUEST)
        self.register()
        duplicate = self.client.post("/api/v1/auth/register/", {"email": "maria@example.com", "password": self.password}, format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_returns_token_pair_and_current_user(self) -> None:
        self.register()
        payload = self.login()

        self.assertIn("access", payload)
        self.assertIn("refresh", payload)
        self.assertEqual(payload["user"]["full_name"], "Maria Schmidt")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {payload['access']}")
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "maria@example.com")

    def test_login_rejects_invalid_credentials(self) -> None:
        self.register()
        response = self.client.post("/api/v1/auth/login/", {"email": "maria@example.com", "password": "wrong-password"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_rotates_refresh_token(self) -> None:
        self.register()
        payload = self.login()
        response = self.client.post("/api/v1/auth/refresh/", {"refresh": payload["refresh"]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertNotEqual(response.data["refresh"], payload["refresh"])

    def test_logout_blacklists_refresh_token(self) -> None:
        self.register()
        payload = self.login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {payload['access']}")

        response = self.client.post("/api/v1/auth/logout/", {"refresh": payload["refresh"]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        refresh = self.client.post("/api/v1/auth/refresh/", {"refresh": payload["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_reset_changes_password_without_email_enumeration(self) -> None:
        self.register()
        old_refresh = self.login()["refresh"]
        known = self.client.post("/api/v1/auth/password/reset/", {"email": "maria@example.com"}, format="json")
        unknown = self.client.post("/api/v1/auth/password/reset/", {"email": "nobody@example.com"}, format="json")
        self.assertEqual(known.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(unknown.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(known.data, unknown.data)

        reset_url = mail.outbox[-1].body.split()[-1]
        params = parse_qs(urlparse(reset_url).query)
        response = self.client.post(
            "/api/v1/auth/password/reset/confirm/",
            {"uidb64": params["uid"][0], "token": params["token"][0], "new_password": "EvenBetterPassword2!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.login(password="EvenBetterPassword2!")
        invalidated = self.client.post("/api/v1/auth/refresh/", {"refresh": old_refresh}, format="json")
        self.assertEqual(invalidated.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_email_verification_marks_user_verified(self) -> None:
        self.register()
        user = User.objects.get(email="maria@example.com")
        response = self.client.post(
            "/api/v1/auth/email/verify/",
            {"uidb64": urlsafe_base64_encode(force_bytes(user.pk)), "token": default_token_generator.make_token(user)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)

    def test_protected_endpoints_require_bearer_authentication(self) -> None:
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.post("/api/v1/auth/logout/", {}).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.post("/api/v1/auth/email/verify/resend/", {}).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_google_oauth_boundary_is_explicitly_unavailable(self) -> None:
        response = self.client.post("/api/v1/auth/oauth/google/", {"id_token": "placeholder"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_501_NOT_IMPLEMENTED)
