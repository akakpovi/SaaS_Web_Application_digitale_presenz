"""Target validation wrapper for the Scanner Engine.

This module is a thin, scanner-layer adapter over ``core.security``, which
already contains a production-grade SSRF implementation.

**Do not duplicate the SSRF logic here.**  The sole purpose of this module
is to provide a stable, scanner-facing API so that individual scanner
implementations do not import directly from ``core``.

Public surface::

    from scanners.security.target_validator import validate_target, TargetInfo

    info = validate_target("https://example.com")
    # info.hostname  → "example.com"
    # info.url       → "https://example.com"
    # info.safe_ips  → ["93.184.216.34"]
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TargetInfo:
    """Validated, SSRF-safe information about a scan target."""

    hostname: str
    """IDNA-normalised, validated public hostname."""

    url: str
    """Canonical URL (scheme + hostname, no path/query/fragment)."""

    safe_ips: list[str] = field(default_factory=list)
    """All DNS-resolved IPs, all verified to be globally routable."""

    scheme: str = "https"
    """URL scheme (always 'http' or 'https')."""


def validate_target(url: str) -> TargetInfo:
    """Validate *url* and return a :class:`TargetInfo`.

    This is the single entry point for scanner-layer target validation.  It
    delegates all SSRF checks to :mod:`core.security` which covers:

    * IDNA hostname normalisation
    * HTTP/HTTPS only, ports 80/443 only
    * No raw IP addresses from user input
    * DNS resolution with all-addresses validation
    * Private / loopback / link-local / multicast blocking
    * Cloud metadata endpoint blocking
    * IPv4 + IPv6 ranges
    * DNS rebinding mitigation

    Raises :class:`scanners.exceptions.TargetValidationError` on any
    security violation so callers don't need to import from ``core``.
    """
    from urllib.parse import urlparse

    from core.security import (
        DomainValidationError,
        SSRFBlockedError,
        _resolve_and_validate,
        validate_domain_for_scan,
    )
    from scanners.exceptions import TargetValidationError

    # Normalise input: strip trailing slashes, inject scheme if missing.
    raw = url.strip().rstrip("/")
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"

    try:
        parsed = urlparse(raw)
        hostname_raw = (parsed.hostname or "").lower().strip()
        scheme = parsed.scheme if parsed.scheme in ("http", "https") else "https"

        # Delegate domain-level validation to core.security.
        hostname = validate_domain_for_scan(hostname_raw)

        # Resolve DNS and block private/loopback/link-local IPs.
        safe_ips = _resolve_and_validate(hostname)

        return TargetInfo(
            hostname=hostname,
            url=f"{scheme}://{hostname}",
            safe_ips=safe_ips,
            scheme=scheme,
        )

    except (DomainValidationError, SSRFBlockedError, ValueError) as exc:
        raise TargetValidationError(str(exc)) from exc


def validate_domain(domain: str) -> str:
    """Validate a bare domain name (no scheme required).

    Convenience wrapper for DNS/email scanners that work with a hostname
    rather than a URL.

    Returns the IDNA-normalised hostname.
    Raises :class:`scanners.exceptions.TargetValidationError` on failure.
    """
    from core.security import DomainValidationError, validate_domain_for_scan
    from scanners.exceptions import TargetValidationError

    try:
        return validate_domain_for_scan(domain)
    except (DomainValidationError, ValueError) as exc:
        raise TargetValidationError(str(exc)) from exc
