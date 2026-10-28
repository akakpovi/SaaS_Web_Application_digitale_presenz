"""Logging redaction for OAuth query parameters.

Nginx and Gunicorn access logs are configured to omit query strings entirely.
This filter is the application-side safety net for Django records such as
``django.request``, whose ``request`` attribute embeds the full callback URL
(including ``code`` and ``state``) on errors.
"""

from __future__ import annotations

import logging
import re

REDACTED = "[REDACTED]"

_SENSITIVE_QUERY_KEYS = (
    "code",
    "state",
    "error_description",
    "access_token",
    "refresh_token",
    "id_token",
    "code_verifier",
)

_SENSITIVE_QUERY_RE = re.compile(
    r"(?i)([?&](?:" + "|".join(_SENSITIVE_QUERY_KEYS) + r")=)[^&\s\"']*"
)


def redact_oauth_query(value: str) -> str:
    """Replace sensitive query-string values with a fixed marker."""

    return _SENSITIVE_QUERY_RE.sub(r"\1" + REDACTED, value)


class OAuthQueryRedactionFilter(logging.Filter):
    """Redact OAuth query values from a log record before it is emitted."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True

        redacted_message = redact_oauth_query(message)
        if redacted_message != message:
            # ``record.msg`` must contain the fully formatted text once args
            # are cleared, otherwise logging would try to format it again.
            record.msg = redacted_message
            record.args = ()

        request = getattr(record, "request", None)
        if request is not None:
            request_text = str(request)
            redacted_request = redact_oauth_query(request_text)
            if redacted_request != request_text:
                record.request = redacted_request

        return True
