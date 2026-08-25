"""Security regression tests for the SSRF-safe scanner transport."""

import unittest
from unittest.mock import MagicMock, patch

from core.security import (
    MAX_REDIRECTS,
    DomainValidationError,
    ResponseTooLargeError,
    SSRFBlockedError,
    _is_ip_safe,
    _resolve_and_validate,
    safe_request,
    validate_domain_for_scan,
)


def addrinfo_ipv4(*addresses: str) -> list[tuple]:
    """Create socket.getaddrinfo-style IPv4 results."""
    return [
        (
            2,  # socket.AF_INET
            1,  # socket.SOCK_STREAM
            6,  # TCP
            "",
            (address, 0),
        )
        for address in addresses
    ]


def addrinfo_ipv6(*addresses: str) -> list[tuple]:
    """Create socket.getaddrinfo-style IPv6 results."""
    return [
        (
            10,  # socket.AF_INET6
            1,   # socket.SOCK_STREAM
            6,
            "",
            (address, 0, 0, 0),
        )
        for address in addresses
    ]


class SecurityTests(unittest.TestCase):
    # ------------------------------------------------------------------
    # Domain validation
    # ------------------------------------------------------------------

    def test_validate_domain_for_scan_valid(self) -> None:
        self.assertEqual(
            validate_domain_for_scan("example.com"),
            "example.com",
        )
        self.assertEqual(
            validate_domain_for_scan("www.example.com"),
            "www.example.com",
        )
        self.assertEqual(
            validate_domain_for_scan(" sub.example.co.uk "),
            "sub.example.co.uk",
        )

        self.assertEqual(
            validate_domain_for_scan("münchen.de"),
            "xn--mnchen-3ya.de",
        )

    def test_validate_domain_for_scan_invalid_format(self) -> None:
        invalid_values = [
            "",
            "http://example.com",
            "https://example.com",
            "example.com/path",
            "example.com?x=1",
            "example.com#fragment",
            "user:pass@example.com",
            "example.com:8080",
            "invalid_domain.com",
            "localhost",
            "-example.com",
            "example-.com",
        ]

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(
                    DomainValidationError
                ):
                    validate_domain_for_scan(value)

    def test_validate_domain_for_scan_internal_suffixes(
        self,
    ) -> None:
        blocked = [
            "localhost",
            "test.local",
            "api.internal",
            "router.home",
            "server.lan",
            "db.corp",
            "service.intranet",
            "host.localdomain",
        ]

        for domain in blocked:
            with self.subTest(domain=domain):
                with self.assertRaises(
                    DomainValidationError
                ):
                    validate_domain_for_scan(domain)

    def test_validate_domain_for_scan_metadata_hostnames(
        self,
    ) -> None:
        blocked = [
            "metadata.google.internal",
            "metadata.google",
            "metadata",
            "169.254.169.254",
            "fd00:ec2::254",
        ]

        for value in blocked:
            with self.subTest(value=value):
                with self.assertRaises(
                    DomainValidationError
                ):
                    validate_domain_for_scan(value)

    def test_validate_domain_for_scan_raw_ip(self) -> None:
        addresses = [
            "8.8.8.8",
            "127.0.0.1",
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "0.0.0.0",
            "2001:4860:4860::8888",
            "::1",
            "fe80::1",
            "fc00::1",
            "fd00::1",
        ]

        for value in addresses:
            with self.subTest(value=value):
                with self.assertRaises(
                    DomainValidationError
                ):
                    validate_domain_for_scan(value)

    # ------------------------------------------------------------------
    # IP safety
    # ------------------------------------------------------------------

    def test_is_ip_safe(self) -> None:
        safe = [
            "8.8.8.8",
            "1.1.1.1",
            "2001:4860:4860::8888",
        ]

        for value in safe:
            with self.subTest(value=value):
                self.assertTrue(
                    _is_ip_safe(value)
                )

        blocked = [
            "127.0.0.1",
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "0.0.0.0",
            "::1",
            "fe80::1",
            "fc00::1",
            "fd00::1",
            "fd00:ec2::254",
            "::ffff:127.0.0.1",
            "::ffff:192.168.1.1",
        ]

        for value in blocked:
            with self.subTest(value=value):
                self.assertFalse(
                    _is_ip_safe(value)
                )

    def test_invalid_ip_is_not_safe(self) -> None:
        self.assertFalse(
            _is_ip_safe("not-an-ip")
        )

    # ------------------------------------------------------------------
    # DNS resolution protection
    # ------------------------------------------------------------------

    @patch("core.security.socket.getaddrinfo")
    def test_resolve_accepts_public_ipv4(
        self,
        mock_getaddrinfo: MagicMock,
    ) -> None:
        mock_getaddrinfo.return_value = (
            addrinfo_ipv4(
                "8.8.8.8",
                "1.1.1.1",
            )
        )

        result = _resolve_and_validate(
            "example.com"
        )

        self.assertEqual(
            result,
            [
                "8.8.8.8",
                "1.1.1.1",
            ],
        )

    @patch("core.security.socket.getaddrinfo")
    def test_resolve_accepts_public_ipv6(
        self,
        mock_getaddrinfo: MagicMock,
    ) -> None:
        mock_getaddrinfo.return_value = (
            addrinfo_ipv6(
                "2001:4860:4860::8888"
            )
        )

        result = _resolve_and_validate(
            "example.com"
        )

        self.assertEqual(
            result,
            ["2001:4860:4860::8888"],
        )

    @patch("core.security.socket.getaddrinfo")
    def test_resolve_blocks_private_ipv4(
        self,
        mock_getaddrinfo: MagicMock,
    ) -> None:
        blocked_addresses = [
            "127.0.0.1",
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
        ]

        for address in blocked_addresses:
            with self.subTest(address=address):
                mock_getaddrinfo.return_value = (
                    addrinfo_ipv4(address)
                )

                with self.assertRaises(
                    SSRFBlockedError
                ):
                    _resolve_and_validate(
                        "attacker.example.com"
                    )

    @patch("core.security.socket.getaddrinfo")
    def test_resolve_blocks_private_ipv6(
        self,
        mock_getaddrinfo: MagicMock,
    ) -> None:
        blocked_addresses = [
            "::1",
            "fe80::1",
            "fc00::1",
            "fd00::1",
            "fd00:ec2::254",
        ]

        for address in blocked_addresses:
            with self.subTest(address=address):
                mock_getaddrinfo.return_value = (
                    addrinfo_ipv6(address)
                )

                with self.assertRaises(
                    SSRFBlockedError
                ):
                    _resolve_and_validate(
                        "attacker.example.com"
                    )

    @patch("core.security.socket.getaddrinfo")
    def test_mixed_public_private_dns_is_rejected(
        self,
        mock_getaddrinfo: MagicMock,
    ) -> None:
        mock_getaddrinfo.return_value = (
            addrinfo_ipv4(
                "8.8.8.8",
                "127.0.0.1",
            )
        )

        with self.assertRaises(
            SSRFBlockedError
        ):
            _resolve_and_validate(
                "mixed.example.com"
            )

    @patch("core.security.socket.getaddrinfo")
    def test_dns_duplicate_addresses_are_deduplicated(
        self,
        mock_getaddrinfo: MagicMock,
    ) -> None:
        mock_getaddrinfo.return_value = (
            addrinfo_ipv4(
                "8.8.8.8",
                "8.8.8.8",
            )
        )

        result = _resolve_and_validate(
            "example.com"
        )

        self.assertEqual(
            result,
            ["8.8.8.8"],
        )

    @patch("core.security.socket.getaddrinfo")
    def test_empty_dns_result_is_rejected(
        self,
        mock_getaddrinfo: MagicMock,
    ) -> None:
        mock_getaddrinfo.return_value = []

        with self.assertRaises(
            SSRFBlockedError
        ):
            _resolve_and_validate(
                "example.com"
            )

    # ------------------------------------------------------------------
    # URL/method/port safety
    # ------------------------------------------------------------------

    def test_safe_request_blocks_unsafe_schemes(self) -> None:
        values = [
            "file:///etc/passwd",
            "ftp://example.com/",
            "gopher://example.com/",
        ]

        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(
                    DomainValidationError
                ):
                    safe_request(value)

    def test_safe_request_blocks_arbitrary_port(self) -> None:
        with self.assertRaises(
            DomainValidationError
        ):
            safe_request(
                "https://example.com:22/"
            )

    def test_safe_request_blocks_credentials(self) -> None:
        with self.assertRaises(
            DomainValidationError
        ):
            safe_request(
                "https://user:password@example.com/"
            )

    def test_safe_request_blocks_fragment(self) -> None:
        with self.assertRaises(
            DomainValidationError
        ):
            safe_request(
                "https://example.com/#secret"
            )

    def test_safe_request_rejects_post_method(self) -> None:
        with self.assertRaises(
            DomainValidationError
        ):
            safe_request(
                "https://example.com/",
                method="POST",
            )

    # ------------------------------------------------------------------
    # Response size and redirect controls
    # ------------------------------------------------------------------

    @patch(
        "core.security._resolve_and_validate",
        return_value=["8.8.8.8"],
    )
    @patch("core.security.urllib3.HTTPSConnectionPool")
    def test_response_content_length_limit(
        self,
        mock_pool_class: MagicMock,
        _mock_resolve: MagicMock,
    ) -> None:
        response = MagicMock()
        response.status = 200
        response.headers = {
            "Content-Length": str(
                (2 * 1024 * 1024) + 1
            )
        }
        response.stream.return_value = []

        pool = MagicMock()
        pool.request.return_value = response
        mock_pool_class.return_value = pool

        with self.assertRaises(
            ResponseTooLargeError
        ):
            safe_request(
                "https://example.com/"
            )

    @patch(
        "core.security._resolve_and_validate",
        return_value=["8.8.8.8"],
    )
    @patch("core.security.urllib3.HTTPSConnectionPool")
    def test_streamed_response_size_limit(
        self,
        mock_pool_class: MagicMock,
        _mock_resolve: MagicMock,
    ) -> None:
        response = MagicMock()
        response.status = 200
        response.headers = {}
        response.stream.return_value = [
            b"a" * (1024 * 1024),
            b"b" * (1024 * 1024),
            b"c",
        ]

        pool = MagicMock()
        pool.request.return_value = response
        mock_pool_class.return_value = pool

        with self.assertRaises(
            ResponseTooLargeError
        ):
            safe_request(
                "https://example.com/"
            )

    @patch(
        "core.security._resolve_and_validate",
        return_value=["8.8.8.8"],
    )
    @patch("core.security.urllib3.HTTPSConnectionPool")
    def test_redirect_to_metadata_hostname_is_blocked(
        self,
        mock_pool_class: MagicMock,
        _mock_resolve: MagicMock,
    ) -> None:
        response = MagicMock()
        response.status = 302
        response.headers = {
            "Location":
                "http://metadata.google.internal/latest/meta-data/"
        }

        pool = MagicMock()
        pool.request.return_value = response
        mock_pool_class.return_value = pool

        with self.assertRaises(
            DomainValidationError
        ):
            safe_request(
                "https://example.com/"
            )

    @patch(
        "core.security._resolve_and_validate",
        return_value=["8.8.8.8"],
    )
    @patch("core.security.urllib3.HTTPSConnectionPool")
    def test_redirect_to_raw_private_ip_is_blocked(
        self,
        mock_pool_class: MagicMock,
        _mock_resolve: MagicMock,
    ) -> None:
        response = MagicMock()
        response.status = 302
        response.headers = {
            "Location":
                "http://127.0.0.1/admin"
        }

        pool = MagicMock()
        pool.request.return_value = response
        mock_pool_class.return_value = pool

        with self.assertRaises(
            DomainValidationError
        ):
            safe_request(
                "https://example.com/"
            )

    @patch(
        "core.security._resolve_and_validate",
        return_value=["8.8.8.8"],
    )
    @patch("core.security.urllib3.HTTPSConnectionPool")
    def test_redirect_to_disallowed_port_is_blocked(
        self,
        mock_pool_class: MagicMock,
        _mock_resolve: MagicMock,
    ) -> None:
        response = MagicMock()
        response.status = 302
        response.headers = {
            "Location":
                "https://example.com:22/"
        }

        pool = MagicMock()
        pool.request.return_value = response
        mock_pool_class.return_value = pool

        with self.assertRaises(
            SSRFBlockedError
        ):
            safe_request(
                "https://example.com/"
            )

    @patch(
        "core.security._resolve_and_validate",
        return_value=["8.8.8.8"],
    )
    @patch("core.security.urllib3.HTTPSConnectionPool")
    def test_redirect_to_disallowed_scheme_is_blocked(
        self,
        mock_pool_class: MagicMock,
        _mock_resolve: MagicMock,
    ) -> None:
        response = MagicMock()
        response.status = 302
        response.headers = {
            "Location":
                "file:///etc/passwd"
        }

        pool = MagicMock()
        pool.request.return_value = response
        mock_pool_class.return_value = pool

        with self.assertRaises(
            SSRFBlockedError
        ):
            safe_request(
                "https://example.com/"
            )

    # ------------------------------------------------------------------
    # TLS hostname / SNI pinning
    # ------------------------------------------------------------------

    @patch(
        "core.security._resolve_and_validate",
        return_value=["8.8.8.8"],
    )
    @patch("core.security.urllib3.HTTPSConnectionPool")
    def test_https_connects_to_validated_ip_with_hostname_verification(
        self,
        mock_pool_class: MagicMock,
        _mock_resolve: MagicMock,
    ) -> None:
        response = MagicMock()
        response.status = 200
        response.headers = {}
        response.stream.return_value = [b"ok"]

        pool = MagicMock()
        pool.request.return_value = response
        mock_pool_class.return_value = pool

        result = safe_request(
            "https://example.com/"
        )

        self.assertEqual(
            result.status_code,
            200,
        )

        mock_pool_class.assert_called_once()

        kwargs = (
            mock_pool_class.call_args.kwargs
        )

        self.assertEqual(
            kwargs["host"],
            "8.8.8.8",
        )
        self.assertEqual(
            kwargs["port"],
            443,
        )
        self.assertEqual(
            kwargs["server_hostname"],
            "example.com",
        )
        self.assertEqual(
            kwargs["assert_hostname"],
            "example.com",
        )

        request_kwargs = (
            pool.request.call_args.kwargs
        )

        self.assertEqual(
            request_kwargs["headers"]["Host"],
            "example.com",
        )


if __name__ == "__main__":
    unittest.main()