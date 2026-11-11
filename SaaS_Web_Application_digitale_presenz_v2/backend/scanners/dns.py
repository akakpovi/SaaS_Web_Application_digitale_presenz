"""DNS resolution scanner."""

import logging
import time
from typing import Any

import dns.resolver

from core.security import DomainValidationError, validate_domain_for_scan
from .base import BaseScanner, ScanResult

logger = logging.getLogger(__name__)


class DNSScanner(BaseScanner):
    """Check DNS resolution."""

    name = "dns"
    timeout = 10

    def scan(self, domain: str) -> ScanResult:
        """Scan DNS configuration."""
        start_time = time.time()
        try:
            validated_domain = validate_domain_for_scan(domain)

            resolver = dns.resolver.Resolver()
            resolver.timeout = self.timeout
            resolver.lifetime = self.timeout

            a_records = []
            try:
                answers = resolver.resolve(validated_domain, "A")
                a_records = [str(rdata) for rdata in answers]
            except dns.resolver.NoAnswer:
                pass

            aaaa_records = []
            try:
                answers = resolver.resolve(validated_domain, "AAAA")
                aaaa_records = [str(rdata) for rdata in answers]
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                pass

            mx_records = []
            try:
                answers = resolver.resolve(validated_domain, "MX")
                mx_records = [str(rdata.exchange) for rdata in answers]
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                pass

            duration_ms = int((time.time() - start_time) * 1000)

            if a_records or aaaa_records:
                return self._create_result(
                    score=15,
                    status="healthy",
                    message=f"DNS resolves correctly ({len(a_records)} A records)",
                    recommendation="",
                    duration_ms=duration_ms,
                    a_records=a_records,
                    aaaa_records=aaaa_records,
                    mx_records=mx_records,
                )
            else:
                return self._create_result(
                    score=0,
                    status="critical",
                    message="DNS resolution failed (no A/AAAA records)",
                    recommendation="Configure A or AAAA records for your domain.",
                    duration_ms=duration_ms,
                )

        except DomainValidationError as e:
            return self._create_result(
                score=0,
                status="critical",
                message=str(e),
                recommendation="Provide a valid, accessible public domain.",
            )
        except dns.resolver.NXDOMAIN:
            return self._create_result(
                score=0,
                status="critical",
                message="Domain does not exist (NXDOMAIN)",
                recommendation="Ensure the domain is registered and nameservers are configured.",
            )
        except dns.resolver.Timeout:
            return self._create_result(
                score=0,
                status="critical",
                message=f"DNS query timeout (>{self.timeout}s)",
                recommendation="Check the nameservers for responsiveness.",
            )
        except Exception as e:
            logger.error(f"DNS scan error for {domain}: {e}")
            return self._create_result(
                score=0,
                status="critical",
                message="DNS scan failed",
                recommendation="Verify the domain's DNS configuration.",
            )


dns_scanner = DNSScanner()
