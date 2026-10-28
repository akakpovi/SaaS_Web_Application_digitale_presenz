"""Language-aware transactional account emails (DE/EN).

Presence targets the German market first, with English as the second supported
language (see ``User.Language``).  Account emails therefore have to be rendered
in the recipient's preferred language instead of a hard-coded English string.

The catalogue is deliberately explicit rather than relying on gettext: the
project ships no compiled ``.mo`` catalogues, so a German ``translation.override``
would silently fall back to the English msgid.  Any language without an entry
falls back to English (the backend ``LANGUAGE_CODE``).
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("de", "en")

_CATALOG: dict[str, dict[str, dict[str, str]]] = {
    "verify_email": {
        "en": {
            "subject": "Verify your Presence email address",
            "body": (
                "Hello,\n\n"
                "please confirm your email address to activate your Presence account:\n\n"
                "{link}\n\n"
                "If you did not create this account, you can safely ignore this message.\n\n"
                "Presence — Digital Presence Monitoring"
            ),
        },
        "de": {
            "subject": "Bestätigen Sie Ihre Presence-E-Mail-Adresse",
            "body": (
                "Guten Tag,\n\n"
                "bitte bestätigen Sie Ihre E-Mail-Adresse, um Ihr Presence-Konto zu aktivieren:\n\n"
                "{link}\n\n"
                "Wenn Sie dieses Konto nicht angelegt haben, können Sie diese Nachricht ignorieren.\n\n"
                "Presence — Digitale Präsenz überwachen"
            ),
        },
    },
    "reset_password": {
        "en": {
            "subject": "Reset your Presence password",
            "body": (
                "Hello,\n\n"
                "you requested a new password for your Presence account. "
                "Open the following link to choose one:\n\n"
                "{link}\n\n"
                "The link expires for security reasons. If you did not request it, "
                "no action is required — your current password stays valid.\n\n"
                "Presence — Digital Presence Monitoring"
            ),
        },
        "de": {
            "subject": "Setzen Sie Ihr Presence-Passwort zurück",
            "body": (
                "Guten Tag,\n\n"
                "Sie haben ein neues Passwort für Ihr Presence-Konto angefordert. "
                "Über den folgenden Link können Sie eines vergeben:\n\n"
                "{link}\n\n"
                "Der Link läuft aus Sicherheitsgründen ab. Falls Sie ihn nicht angefordert "
                "haben, ist keine Aktion erforderlich — Ihr aktuelles Passwort bleibt gültig.\n\n"
                "Presence — Digitale Präsenz überwachen"
            ),
        },
    },
}


def normalize_language(language_code: str | None) -> str:
    """Return a supported e-mail language code, falling back to English."""
    code = (language_code or "").strip().lower().replace("_", "-")
    base = code.split("-")[0]
    return base if base in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def render_account_email(
    kind: str, language_code: str | None, **context: str
) -> tuple[str, str]:
    """Render ``(subject, body)`` for an account e-mail in the recipient language."""
    if kind not in _CATALOG:
        raise ValueError(f"Unknown account e-mail kind: {kind}")

    language = normalize_language(language_code)
    template = _CATALOG[kind][language]
    return template["subject"], template["body"].format(**context)
