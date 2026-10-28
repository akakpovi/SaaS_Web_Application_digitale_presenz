"""SSRF-safe validation and HTTP transport for website scanners.

This module is the security boundary between untrusted domain input and outbound
network requests.

Security properties:
- IDNA hostname normalization
- Strict hostname validation
- Raw IP rejection for public scan input
- HTTP/HTTPS only
- Ports 80/443 only
- No URL credentials or fragments
- Internal/reserved hostname blocking
- DNS resolution before connection
- All resolved addresses must be globally routable
- DNS rebinding mitigation by connecting to a pre-validated IP
- TLS SNI and certificate verification against the original hostname
- Manual redirect handling with full validation on every hop
- Redirect count limits
- Response body size limits
- Connection/read timeouts

New scanners must use ``safe_request`` rather than raw HTTP clients.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import socket
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

import certifi
import urllib3


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_DOMAIN_LENGTH = 253
MAX_LABEL_LENGTH = 63

MAX_REDIRECTS = 3

DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_READ_TIMEOUT = 15.0

MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MiB

ALLOWED_PORTS = frozenset({80, 443})
ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_METHODS = frozenset({"GET", "HEAD"})


_INTERNAL_SUFFIXES = frozenset(
    {
        "localhost",
        "local",
        "internal",
        "home",
        "lan",
        "intranet",
        "corp",
        "localdomain",
        "test",
        "invalid",
        "example",
    }
)


_METADATA_HOSTNAMES = frozenset(
    {
        "metadata",
        "metadata.google",
        "metadata.google.internal",
    }
)


_METADATA_IPS = frozenset(
    {
        "169.254.169.254",
        "fd00:ec2::254",
        # Alibaba Cloud metadata service.
        "100.100.100.200",
    }
)


_DOMAIN_RE = re.compile(
    r"^(?!-)"
    r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
    r"(?:\."
    r"(?!-)"
    r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
    r")*$"
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DomainValidationError(ValueError):
    """Raised when a domain or URL fails validation."""


class SSRFBlockedError(DomainValidationError):
    """Raised when a target resolves or redirects to an unsafe destination."""


class ResponseTooLargeError(Exception):
    """Raised when a response exceeds the configured size limit."""


# ---------------------------------------------------------------------------
# Domain validation
# ---------------------------------------------------------------------------


def _is_ip_literal(value: str) -> bool:
    """Return whether ``value`` is an IPv4 or IPv6 literal."""

    candidate = value.strip()

    # Accept bracketed IPv6 for detection purposes.
    if (
        candidate.startswith("[")
        and candidate.endswith("]")
    ):
        candidate = candidate[1:-1]

    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return False

    return True


def validate_domain_for_scan(domain: str) -> str:
    """Validate and normalize a public domain.

    Only a hostname is accepted here, not a complete URL.

    Returns:
        Normalized ASCII/IDNA hostname.

    Raises:
        DomainValidationError: if the hostname is invalid or prohibited.
    """

    if not isinstance(domain, str):
        raise DomainValidationError(
            "Domain is required."
        )

    domain = domain.strip()

    if not domain:
        raise DomainValidationError(
            "Domain is required."
        )

    domain = domain.lower().rstrip(".")

    if not domain:
        raise DomainValidationError(
            "Domain is required."
        )

    # Reject complete URLs, paths, queries and fragments.
    if (
        "://" in domain
        or "/" in domain
        or "?" in domain
        or "#" in domain
    ):
        raise DomainValidationError(
            "Enter a domain name without a scheme, path, or query."
        )

    if "@" in domain:
        raise DomainValidationError(
            "Credentials in domain are not allowed."
        )

    # Reject raw IP literals before generic ":" rejection so IPv6 is
    # classified correctly.
    if _is_ip_literal(domain):
        raise DomainValidationError(
            "Raw IP addresses are not allowed."
        )

    # Remaining ":" generally indicates an explicit port.
    if ":" in domain:
        raise DomainValidationError(
            "Port specifications are not allowed."
        )

    try:
        ascii_domain = (
            domain
            .encode("idna")
            .decode("ascii")
        )
    except UnicodeError as exc:
        raise DomainValidationError(
            "Invalid internationalized domain name."
        ) from exc

    ascii_domain = ascii_domain.lower()

    if len(ascii_domain) > MAX_DOMAIN_LENGTH:
        raise DomainValidationError(
            f"Domain exceeds {MAX_DOMAIN_LENGTH} characters."
        )

    labels = ascii_domain.split(".")

    # Do not permit single-label/internal-style hosts.
    if len(labels) < 2:
        raise DomainValidationError(
            "Single-label hostnames are not allowed."
        )

    for label in labels:
        if not label:
            raise DomainValidationError(
                "Domain contains an empty label."
            )

        if len(label) > MAX_LABEL_LENGTH:
            raise DomainValidationError(
                f"Domain label exceeds {MAX_LABEL_LENGTH} characters."
            )

        if (
            label.startswith("-")
            or label.endswith("-")
        ):
            raise DomainValidationError(
                "Labels must not start or end with a hyphen."
            )

    if not _DOMAIN_RE.fullmatch(ascii_domain):
        raise DomainValidationError(
            "Domain contains invalid characters."
        )

    for suffix in _INTERNAL_SUFFIXES:
        if (
            ascii_domain == suffix
            or ascii_domain.endswith(
                f".{suffix}"
            )
        ):
            raise DomainValidationError(
                "Internal hostnames are not allowed."
            )

    if ascii_domain in _METADATA_HOSTNAMES:
        raise DomainValidationError(
            "Metadata endpoints are not allowed."
        )

    return ascii_domain


# ---------------------------------------------------------------------------
# IP validation
# ---------------------------------------------------------------------------


def _is_ip_safe(addr: str) -> bool:
    """Return whether an address is safe for public outbound scanning.

    A positive allow policy is used: only addresses considered globally
    routable by Python's ``ipaddress`` module are accepted.
    """

    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False

    # IPv4 represented inside IPv6 must be validated as IPv4.
    if (
        isinstance(ip, ipaddress.IPv6Address)
        and ip.ipv4_mapped is not None
    ):
        return _is_ip_safe(
            str(ip.ipv4_mapped)
        )

    normalized = str(ip)

    if normalized in _METADATA_IPS:
        return False

    return ip.is_global


def _resolve_and_validate(
    hostname: str,
) -> list[str]:
    """Resolve hostname and require every result to be safe.

    A hostname resolving to a mixture of public and prohibited addresses is
    rejected entirely rather than selecting only a public address.
    """

    try:
        results = socket.getaddrinfo(
            hostname,
            None,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
        )

    except socket.gaierror as exc:
        logger.warning(
            "dns_resolution_failed",
            extra={
                "hostname": hostname,
            },
        )

        raise SSRFBlockedError(
            "The target domain could not be resolved safely."
        ) from exc

    addresses: list[str] = []

    for (
        _family,
        _socktype,
        _protocol,
        _canonical_name,
        sockaddr,
    ) in results:
        if not sockaddr:
            continue

        ip_str = str(
            sockaddr[0]
        )

        if ip_str not in addresses:
            addresses.append(
                ip_str
            )

    if not addresses:
        raise SSRFBlockedError(
            "The target domain could not be resolved safely."
        )

    for ip_str in addresses:
        if not _is_ip_safe(ip_str):
            logger.warning(
                "ssrf_blocked_ip",
                extra={
                    "hostname": hostname,
                    "ip": ip_str,
                },
            )

            raise SSRFBlockedError(
                "The target resolves to a prohibited network address."
            )

    return addresses


def resolve_public_ip(hostname: str) -> str:
    """Validate a public hostname and return one validated, public IP.

    This is the safe replacement for ``socket.gethostbyname``: it rejects raw
    IP literals and internal hostnames, resolves the name, and refuses any
    result that is not globally routable (loopback, private, link-local,
    metadata, ...).

    Raises:
        DomainValidationError: if the hostname is invalid, internal, or
            resolves to a prohibited address.
    """

    validated_hostname = validate_domain_for_scan(hostname)
    addresses = _resolve_and_validate(validated_hostname)
    return addresses[0]


# ---------------------------------------------------------------------------
# Response object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SafeResponse:
    """Sanitized result from an SSRF-safe HTTP request."""

    status_code: int
    headers: dict[str, str]
    body: bytes
    url: str
    elapsed_ms: int
    redirect_chain: list[str] = field(
        default_factory=list
    )


# ---------------------------------------------------------------------------
# Public safe HTTP API
# ---------------------------------------------------------------------------


def safe_request(
    url: str,
    *,
    method: str = "GET",
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
    read_timeout: float = DEFAULT_READ_TIMEOUT,
    max_bytes: int = MAX_RESPONSE_BYTES,
    headers: dict[str, str] | None = None,
    stream_body: bool = True,
) -> SafeResponse:
    """Perform an SSRF-resistant HTTP request.

    DNS is resolved and validated before connecting. The connection is then made
    directly to the validated IP while preserving the original hostname for the
    HTTP Host header, TLS SNI and certificate hostname verification.

    Redirects are handled manually and fully revalidated.
    """

    method = method.upper()

    if method not in ALLOWED_METHODS:
        raise DomainValidationError(
            "HTTP method is not allowed."
        )

    if connect_timeout <= 0:
        raise ValueError(
            "connect_timeout must be greater than zero."
        )

    if read_timeout <= 0:
        raise ValueError(
            "read_timeout must be greater than zero."
        )

    if max_bytes <= 0:
        raise ValueError(
            "max_bytes must be greater than zero."
        )

    parsed = urlparse(
        url
    )

    scheme = (
        parsed.scheme
        .lower()
    )

    if scheme not in ALLOWED_SCHEMES:
        raise DomainValidationError(
            "Only HTTP and HTTPS are allowed."
        )

    hostname = (
        parsed.hostname
        or ""
    )

    if not hostname:
        raise DomainValidationError(
            "URL hostname is required."
        )

    try:
        explicit_port = parsed.port
    except ValueError as exc:
        raise DomainValidationError(
            "Invalid URL port."
        ) from exc

    effective_port = (
        explicit_port
        or (
            443
            if scheme == "https"
            else 80
        )
    )

    if effective_port not in ALLOWED_PORTS:
        raise DomainValidationError(
            "The requested port is not allowed."
        )

    if (
        parsed.username
        or parsed.password
    ):
        raise DomainValidationError(
            "Credentials in URLs are not allowed."
        )

    if parsed.fragment:
        raise DomainValidationError(
            "URL fragments are not allowed."
        )

    validated_hostname = (
        validate_domain_for_scan(
            hostname
        )
    )

    safe_ips = (
        _resolve_and_validate(
            validated_hostname
        )
    )

    path = (
        parsed.path
        or "/"
    )

    if parsed.query:
        path = (
            f"{path}?"
            f"{parsed.query}"
        )

    started_at = (
        time.monotonic()
    )

    return _do_request(
        scheme=scheme,
        hostname=validated_hostname,
        target_ip=safe_ips[0],
        port=effective_port,
        path=path,
        method=method,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        max_bytes=max_bytes,
        request_headers=headers or {},
        redirect_chain=[],
        redirects_remaining=MAX_REDIRECTS,
        stream_body=stream_body,
        request_started=started_at,
    )


def safe_webhook_request(
    url: str,
    *,
    json_payload: Any | None = None,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
    read_timeout: float = DEFAULT_READ_TIMEOUT,
    max_bytes: int = MAX_RESPONSE_BYTES,
    headers: dict[str, str] | None = None,
) -> SafeResponse:
    """Perform an SSRF-resistant HTTP POST for outbound webhooks.

    ``safe_request`` is intentionally restricted to GET/HEAD (see
    ``ALLOWED_METHODS``). User-configured webhooks must POST a JSON payload, so
    this variant reuses the exact same validation and DNS-pinning pipeline
    while allowing POST. Only HTTP/HTTPS on ports 80/443 are accepted, and the
    connection is made to a pre-validated public IP.

    Raises:
        DomainValidationError: if the URL, hostname or resolved address is not
            safe (internal, private, metadata, prohibited port, ...).
    """

    parsed = urlparse(url)

    scheme = parsed.scheme.lower()

    if scheme not in ALLOWED_SCHEMES:
        raise DomainValidationError(
            "Only HTTP and HTTPS are allowed."
        )

    hostname = parsed.hostname or ""

    if not hostname:
        raise DomainValidationError(
            "URL hostname is required."
        )

    try:
        explicit_port = parsed.port
    except ValueError as exc:
        raise DomainValidationError(
            "Invalid URL port."
        ) from exc

    effective_port = (
        explicit_port
        or (443 if scheme == "https" else 80)
    )

    if effective_port not in ALLOWED_PORTS:
        raise DomainValidationError(
            "The requested port is not allowed."
        )

    if parsed.username or parsed.password:
        raise DomainValidationError(
            "Credentials in URLs are not allowed."
        )

    if parsed.fragment:
        raise DomainValidationError(
            "URL fragments are not allowed."
        )

    validated_hostname = validate_domain_for_scan(hostname)
    safe_ips = _resolve_and_validate(validated_hostname)

    path = parsed.path or "/"

    if parsed.query:
        path = f"{path}?{parsed.query}"

    request_headers = dict(headers or {})
    body: bytes | None = None

    if json_payload is not None:
        body = json.dumps(json_payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request_headers.setdefault("Accept", "application/json")

    started_at = time.monotonic()

    return _do_request(
        scheme=scheme,
        hostname=validated_hostname,
        target_ip=safe_ips[0],
        port=effective_port,
        path=path,
        method="POST",
        body=body,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        max_bytes=max_bytes,
        request_headers=request_headers,
        redirect_chain=[],
        redirects_remaining=MAX_REDIRECTS,
        stream_body=True,
        request_started=started_at,
    )


# ---------------------------------------------------------------------------
# Internal HTTP implementation
# ---------------------------------------------------------------------------


def _do_request(
    *,
    scheme: str,
    hostname: str,
    target_ip: str,
    port: int,
    path: str,
    method: str,
    body: bytes | None = None,
    connect_timeout: float,
    read_timeout: float,
    max_bytes: int,
    request_headers: dict[str, str],
    redirect_chain: list[str],
    redirects_remaining: int,
    stream_body: bool,
    request_started: float,
) -> SafeResponse:
    """Execute one validated HTTP hop.

    The TCP connection is made to ``target_ip`` while ``hostname`` remains the
    logical hostname used for HTTP and TLS validation.
    """

    if not path.startswith("/"):
        path = (
            f"/{path}"
        )

    default_port = (
        443
        if scheme == "https"
        else 80
    )

    if port == default_port:
        authority = hostname
    else:
        authority = (
            f"{hostname}:{port}"
        )

    display_url = (
        f"{scheme}://"
        f"{authority}"
        f"{path}"
    )

    merged_headers = {
        "Host": authority,
        "User-Agent": (
            "Presence-Scanner/1.0"
        ),
        "Accept": (
            "text/html,"
            "application/xhtml+xml,"
            "application/xml;q=0.9,"
            "*/*;q=0.8"
        ),
        **request_headers,
    }

    timeout = urllib3.Timeout(
        connect=connect_timeout,
        read=read_timeout,
    )

    pool: (
        urllib3.HTTPConnectionPool
        | urllib3.HTTPSConnectionPool
    )

    if scheme == "https":
        pool = (
            urllib3.HTTPSConnectionPool(
                host=target_ip,
                port=port,
                timeout=timeout,
                retries=False,
                cert_reqs="CERT_REQUIRED",
                ca_certs=certifi.where(),
                server_hostname=hostname,
                assert_hostname=hostname,
            )
        )
    else:
        pool = (
            urllib3.HTTPConnectionPool(
                host=target_ip,
                port=port,
                timeout=timeout,
                retries=False,
            )
        )

    response: (
        urllib3.HTTPResponse
        | None
    ) = None

    try:
        response = pool.request(
            method=method,
            url=path,
            body=body,
            headers=merged_headers,
            preload_content=False,
            redirect=False,
        )

        status_code = int(
            response.status
        )

        response_headers = {
            str(key): str(value)
            for key, value
            in response.headers.items()
        }

        # ---------------------------------------------------------------
        # Redirects
        # ---------------------------------------------------------------

        location = (
            response.headers.get(
                "Location"
            )
        )

        if (
            300 <= status_code < 400
            and location
        ):
            if redirects_remaining <= 0:
                raise DomainValidationError(
                    f"Too many redirects "
                    f"(max {MAX_REDIRECTS})."
                )

            location = str(
                location
            )

            absolute_redirect_url = (
                urljoin(
                    display_url,
                    location,
                )
            )

            redirect_parsed = (
                urlparse(
                    absolute_redirect_url
                )
            )

            redirect_scheme = (
                redirect_parsed.scheme
                .lower()
            )

            if (
                redirect_scheme
                not in ALLOWED_SCHEMES
            ):
                raise SSRFBlockedError(
                    "Redirect target uses a prohibited scheme."
                )

            redirect_hostname = (
                redirect_parsed.hostname
                or ""
            )

            if not redirect_hostname:
                raise SSRFBlockedError(
                    "Redirect target has no hostname."
                )

            try:
                redirect_explicit_port = (
                    redirect_parsed.port
                )
            except ValueError as exc:
                raise SSRFBlockedError(
                    "Redirect target contains an invalid port."
                ) from exc

            redirect_port = (
                redirect_explicit_port
                or (
                    443
                    if redirect_scheme
                    == "https"
                    else 80
                )
            )

            if (
                redirect_port
                not in ALLOWED_PORTS
            ):
                raise SSRFBlockedError(
                    "Redirect target uses a prohibited port."
                )

            if (
                redirect_parsed.username
                or redirect_parsed.password
            ):
                raise SSRFBlockedError(
                    "Redirect target contains credentials."
                )

            if redirect_parsed.fragment:
                raise SSRFBlockedError(
                    "Redirect target contains a fragment."
                )

            validated_redirect_hostname = (
                validate_domain_for_scan(
                    redirect_hostname
                )
            )

            redirect_ips = (
                _resolve_and_validate(
                    validated_redirect_hostname
                )
            )

            redirect_path = (
                redirect_parsed.path
                or "/"
            )

            if redirect_parsed.query:
                redirect_path = (
                    f"{redirect_path}?"
                    f"{redirect_parsed.query}"
                )

            new_redirect_chain = [
                *redirect_chain,
                absolute_redirect_url,
            ]

            response.release_conn()
            response = None

            pool.close()

            return _do_request(
                scheme=redirect_scheme,
                hostname=validated_redirect_hostname,
                target_ip=redirect_ips[0],
                port=redirect_port,
                path=redirect_path,
                method=method,
                body=body,
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                max_bytes=max_bytes,
                request_headers=request_headers,
                redirect_chain=new_redirect_chain,
                redirects_remaining=(
                    redirects_remaining
                    - 1
                ),
                stream_body=stream_body,
                request_started=request_started,
            )

        # ---------------------------------------------------------------
        # Body size validation
        # ---------------------------------------------------------------

        content_length = (
            response.headers.get(
                "Content-Length"
            )
        )

        if content_length:
            try:
                declared_length = int(
                    content_length
                )
            except (
                TypeError,
                ValueError,
            ):
                declared_length = None

            if (
                declared_length is not None
                and declared_length > max_bytes
            ):
                raise ResponseTooLargeError(
                    "Response exceeds the configured size limit."
                )

        body = b""

        if stream_body:
            chunks: list[bytes] = []
            total = 0

            for chunk in response.stream(
                amt=8192,
                decode_content=True,
            ):
                if not chunk:
                    continue

                total += len(
                    chunk
                )

                if total > max_bytes:
                    raise ResponseTooLargeError(
                        "Response exceeds the configured size limit."
                    )

                chunks.append(
                    chunk
                )

            body = b"".join(
                chunks
            )

        else:
            # HEAD normally has no response body. For non-HEAD requests that
            # explicitly disable streaming, enforce the same hard size limit.
            if method != "HEAD":
                data = (
                    response.data
                    or b""
                )

                if len(data) > max_bytes:
                    raise ResponseTooLargeError(
                        "Response exceeds the configured size limit."
                    )

                body = data

        elapsed_ms = max(
            1,
            round(
                (
                    time.monotonic()
                    - request_started
                )
                * 1000
            ),
        )

        return SafeResponse(
            status_code=status_code,
            headers=response_headers,
            body=body,
            url=display_url,
            elapsed_ms=elapsed_ms,
            redirect_chain=(
                list(
                    redirect_chain
                )
            ),
        )

    except (
        urllib3.exceptions.SSLError
    ) as exc:
        logger.warning(
            "safe_http_tls_error",
            extra={
                "hostname": hostname,
            },
        )

        raise DomainValidationError(
            "TLS validation failed."
        ) from exc

    except (
        urllib3.exceptions.ConnectTimeoutError
    ) as exc:
        logger.warning(
            "safe_http_connect_timeout",
            extra={
                "hostname": hostname,
            },
        )

        raise DomainValidationError(
            "Connection timed out."
        ) from exc

    except (
        urllib3.exceptions.ReadTimeoutError
    ) as exc:
        logger.warning(
            "safe_http_read_timeout",
            extra={
                "hostname": hostname,
            },
        )

        raise DomainValidationError(
            "The remote server timed out."
        ) from exc

    except (
        urllib3.exceptions.HTTPError
    ) as exc:
        logger.warning(
            "safe_http_error",
            extra={
                "hostname": hostname,
            },
        )

        raise DomainValidationError(
            "The remote server could not be reached."
        ) from exc

    finally:
        if response is not None:
            try:
                response.release_conn()
            except Exception:
                logger.debug(
                    "response_release_failed",
                    exc_info=True,
                )

        pool.close()


# ---------------------------------------------------------------------------
# Legacy compatibility
# ---------------------------------------------------------------------------


def get_safe_request_kwargs(
    timeout: int = 30,
) -> dict[str, Any]:
    """Return legacy request kwargs.

    Deprecated.

    New scanner implementations must use ``safe_request`` because these kwargs
    alone do not provide DNS pinning, redirect revalidation, or full SSRF
    protection.
    """

    return {
        "timeout": (
            DEFAULT_CONNECT_TIMEOUT,
            float(timeout),
        ),
        "allow_redirects": False,
        "stream": True,
        "headers": {
            "User-Agent":
                "Presence-Scanner/1.0",
        },
        "verify": True,
    }