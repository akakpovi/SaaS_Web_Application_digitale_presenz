"""Scanner feature flags.

Advanced security tools (ZAP, Nuclei) send real attack payloads.  They must
never run automatically on customer sites until the operator has explicitly
opted in, even when the binaries/images happen to be installed.  Every entry
point of those adapters checks :func:`advanced_security_enabled` as a second
line of defence; the orchestrator also skips their steps entirely.
"""

from __future__ import annotations

from django.conf import settings


def advanced_security_enabled() -> bool:
    """Return True only when the advanced security tier is explicitly enabled."""
    return bool(getattr(settings, "SCANNER_ADVANCED_SECURITY_ENABLED", False))
