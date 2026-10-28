import io
import json
import logging

from django.conf import settings
from django.test import SimpleTestCase
from pythonjsonlogger.json import JsonFormatter

from integrations.logging import OAuthQueryRedactionFilter, redact_oauth_query


class OAuthQueryRedactionTests(SimpleTestCase):
    def test_redacts_code_and_state_from_formatted_message(self):
        record = logging.LogRecord(
            "django.request",
            logging.WARNING,
            __file__,
            1,
            "Bad Request: %s",
            (
                "/api/v1/social/oauth/linkedin/callback/"
                "?code=SECRET-CODE&state=SECRET-STATE",
            ),
            None,
        )

        self.assertTrue(OAuthQueryRedactionFilter().filter(record))
        message = record.getMessage()
        self.assertNotIn("SECRET-CODE", message)
        self.assertNotIn("SECRET-STATE", message)
        self.assertIn("code=[REDACTED]", message)
        self.assertIn("state=[REDACTED]", message)

    def test_redacts_request_attribute(self):
        record = logging.LogRecord(
            "django.request",
            logging.WARNING,
            __file__,
            1,
            "Bad Request: /callback/",
            (),
            None,
        )
        record.request = (
            "<WSGIRequest: GET '/api/v1/social/oauth/linkedin/callback/"
            "?code=SECRET-CODE&state=SECRET-STATE'>"
        )

        self.assertTrue(OAuthQueryRedactionFilter().filter(record))
        self.assertNotIn("SECRET-CODE", str(record.request))
        self.assertNotIn("SECRET-STATE", str(record.request))
        self.assertIn("code=[REDACTED]", str(record.request))
        self.assertIn("state=[REDACTED]", str(record.request))

    def test_redacts_provider_error_description_and_tokens(self):
        value = (
            "/callback/?error=access_denied"
            "&error_description=SECRET-DESCRIPTION"
            "&access_token=SECRET-ACCESS"
            "&refresh_token=SECRET-REFRESH"
        )

        redacted = redact_oauth_query(value)
        self.assertNotIn("SECRET-DESCRIPTION", redacted)
        self.assertNotIn("SECRET-ACCESS", redacted)
        self.assertNotIn("SECRET-REFRESH", redacted)
        self.assertIn("error_description=[REDACTED]", redacted)
        self.assertIn("access_token=[REDACTED]", redacted)
        self.assertIn("refresh_token=[REDACTED]", redacted)

    def test_non_sensitive_record_is_unchanged(self):
        record = logging.LogRecord(
            "integrations.oauth",
            logging.INFO,
            __file__,
            1,
            "oauth_authorize_created org=%s provider=%s",
            ("org-id", "linkedin"),
            None,
        )

        self.assertTrue(OAuthQueryRedactionFilter().filter(record))
        self.assertEqual(
            record.getMessage(),
            "oauth_authorize_created org=org-id provider=linkedin",
        )


class ServerLoggingConfigurationTests(SimpleTestCase):
    """Prove the production logging path, not only the regex helper."""

    def test_console_and_server_handlers_install_the_redaction_filter(self):
        self.assertIn(
            "redact_oauth_query",
            settings.LOGGING["handlers"]["console"]["filters"],
        )
        self.assertIn(
            "redact_oauth_query",
            settings.LOGGING["loggers"]["django.server"]["filters"],
        )

    def test_json_handler_output_never_contains_callback_secrets(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(
            JsonFormatter(
                "%(levelname)s %(name)s %(message)s %(request)s"
            )
        )
        handler.addFilter(OAuthQueryRedactionFilter())

        logger = logging.getLogger("presence.tests.django.request")
        previous_handlers = logger.handlers[:]
        previous_propagate = logger.propagate
        previous_level = logger.level
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.WARNING)
        try:
            callback_url = (
                "/api/v1/social/oauth/linkedin/callback/"
                "?code=SECRET-CODE&state=SECRET-STATE"
            )
            logger.warning(
                "Bad Request: %s",
                f"<WSGIRequest: GET '{callback_url}'>",
                extra={"request": f"<WSGIRequest: GET '{callback_url}'>"},
            )
        finally:
            logger.handlers = previous_handlers
            logger.propagate = previous_propagate
            logger.setLevel(previous_level)

        output = stream.getvalue()
        payload = json.loads(output)

        self.assertNotIn("SECRET-CODE", output)
        self.assertNotIn("SECRET-STATE", output)
        self.assertIn("code=[REDACTED]", payload["message"])
        self.assertIn("state=[REDACTED]", payload["request"])

    def test_gunicorn_access_log_format_omits_the_query_string(self):
        dockerfile = settings.BASE_DIR / "Dockerfile"
        contents = dockerfile.read_text(encoding="utf-8")
        access_format = next(
            line
            for line in contents.splitlines()
            if "--access-logformat" in line
        )

        self.assertIn("%(U)s", access_format)
        self.assertNotIn("%(r)s", access_format)
        self.assertNotIn("$(request)", access_format)
