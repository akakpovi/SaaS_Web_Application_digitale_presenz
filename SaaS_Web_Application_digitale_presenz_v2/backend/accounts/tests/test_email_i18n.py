"""German/English transactional account e-mails.

The German launch requires account e-mails (verification, password reset) to be
written in the recipient's language.  The catalogue is explicit — the project
ships no compiled gettext catalogues — so these tests assert the real German
subject and body instead of only checking ``translation.get_language()``.
"""

from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.emails import normalize_language, render_account_email
from accounts.models import User
from accounts.services import send_password_reset_email, send_verification_email

REGISTER_URL = "/api/v1/auth/register/"
PASSWORD_RESET_URL = "/api/v1/auth/password/reset/"
PASSWORD = "a-strong-test-passphrase-42"


class AccountEmailLanguageTests(TestCase):
    def setUp(self):
        mail.outbox = []

    def test_german_user_receives_german_verification_email(self):
        user = User.objects.create_user(
            email="de@example.com", password=PASSWORD, language="de"
        )

        self.assertTrue(send_verification_email(user))

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["de@example.com"])
        self.assertEqual(message.subject, "Bestätigen Sie Ihre Presence-E-Mail-Adresse")
        self.assertIn("/verify-email?uid=", message.body)
        self.assertIn("E-Mail-Adresse", message.body)

    def test_english_user_receives_english_verification_email(self):
        user = User.objects.create_user(
            email="en@example.com", password=PASSWORD, language="en"
        )

        send_verification_email(user)

        self.assertEqual(mail.outbox[0].subject, "Verify your Presence email address")
        self.assertIn("/verify-email?uid=", mail.outbox[0].body)

    def test_language_outside_the_catalogue_falls_back_to_english(self):
        """``fr`` is a stored profile value but has no catalogue entry."""
        user = User.objects.create_user(
            email="fr@example.com", password=PASSWORD, language="fr"
        )

        send_verification_email(user)

        self.assertEqual(normalize_language("fr"), "en")
        self.assertEqual(mail.outbox[0].subject, "Verify your Presence email address")

    def test_german_password_reset_email(self):
        user = User.objects.create_user(
            email="de-reset@example.com", password=PASSWORD, language="de"
        )

        self.assertTrue(send_password_reset_email(user))

        message = mail.outbox[0]
        self.assertEqual(message.subject, "Setzen Sie Ihr Presence-Passwort zurück")
        self.assertIn("/reset-password?uid=", message.body)

    def test_english_password_reset_email(self):
        user = User.objects.create_user(
            email="en-reset@example.com", password=PASSWORD, language="en"
        )

        send_password_reset_email(user)

        self.assertEqual(mail.outbox[0].subject, "Reset your Presence password")

    def test_unknown_template_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            render_account_email("does-not-exist", "de")


class RegistrationLanguageTests(TestCase):
    """The sign-up language decides the language of the first account e-mail."""

    def setUp(self):
        self.client = APIClient()
        mail.outbox = []

    def test_german_sign_up_creates_german_account_and_email(self):
        response = self.client.post(
            REGISTER_URL,
            {
                "email": "anmeldung@example.com",
                "full_name": "Anna Beispiel",
                "password": PASSWORD,
                "language": "de",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(User.objects.get(email="anmeldung@example.com").language, "de")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject, "Bestätigen Sie Ihre Presence-E-Mail-Adresse"
        )

    def test_sign_up_without_language_keeps_english_default(self):
        response = self.client.post(
            REGISTER_URL,
            {"email": "default@example.com", "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(User.objects.get(email="default@example.com").language, "en")
        self.assertEqual(mail.outbox[0].subject, "Verify your Presence email address")

    def test_unsupported_language_code_is_rejected(self):
        response = self.client.post(
            REGISTER_URL,
            {
                "email": "zz@example.com",
                "password": PASSWORD,
                "language": "zz",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("language", response.data)
        self.assertFalse(User.objects.filter(email="zz@example.com").exists())

    def test_password_reset_uses_the_stored_profile_language(self):
        User.objects.create_user(
            email="reset-de@example.com", password=PASSWORD, language="de"
        )

        response = self.client.post(
            PASSWORD_RESET_URL, {"email": "reset-de@example.com"}, format="json"
        )

        # 202 (not 200): the endpoint never reveals whether the account exists.
        self.assertEqual(response.status_code, 202, response.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject, "Setzen Sie Ihr Presence-Passwort zurück"
        )
