from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class ProfileAPITests(APITestCase):
    url = "/api/v1/users/profile/"

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="profile@example.com", password="ProfilePassword1!"
        )

    def test_profile_requires_authentication(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_returns_real_defaults(self) -> None:
        self.client.force_authenticate(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "language": "en",
                "business_name": "",
                "business_industry": "",
                "business_country": "",
                "timezone": "Europe/Berlin",
            },
        )

    def test_patch_persists_business_and_language(self) -> None:
        self.client.force_authenticate(self.user)

        response = self.client.patch(
            self.url,
            {
                "language": "fr",
                "business_name": "Boulangerie Martin",
                "business_industry": "restaurant",
                "business_country": "FR",
                "timezone": "Europe/Paris",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.language, "fr")
        self.assertEqual(self.user.business_name, "Boulangerie Martin")
        self.assertEqual(self.user.business_industry, "restaurant")
        self.assertEqual(self.user.business_country, "FR")
        self.assertEqual(self.user.timezone, "Europe/Paris")

        self.assertEqual(
            self.client.get(self.url).data["business_name"], "Boulangerie Martin"
        )

    def test_patch_rejects_unknown_choices(self) -> None:
        self.client.force_authenticate(self.user)

        response = self.client.patch(
            self.url, {"language": "xx", "timezone": "Mars/Olympus"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("language", response.data)
        self.assertIn("timezone", response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.language, "en")

    def test_profile_is_scoped_to_the_authenticated_user(self) -> None:
        other = User.objects.create_user(
            email="other@example.com", password="OtherPassword1!"
        )
        self.client.force_authenticate(self.user)

        self.client.patch(self.url, {"business_name": "Mine"}, format="json")

        other.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.user.business_name, "Mine")
        self.assertEqual(other.business_name, "")
