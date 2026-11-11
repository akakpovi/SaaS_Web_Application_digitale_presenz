"""Email security scanner."""

import logging
import time
from typing import Any

import dns.resolver

from core.security import DomainValidationError, validate_domain_for_scan
from .base import BaseScanner, ScanResult

logger = logging.getLogger(__name__)


class EmailSecurityScanner(BaseScanner):
    """Check email security records."""

    name = "email_security"
    timeout = 10

    def scan(self, domain: str) -> ScanResult:
        """Scan email security configuration."""
        start_time = time.time()
        try:
            validated_domain = validate_domain_for_scan(domain)

            resolver = dns.resolver.Resolver()
            resolver.timeout = self.timeout
            resolver.lifetime = self.timeout

            spf_record = None
            try:
                answers = resolver.resolve(validated_domain, "TXT")
                for rdata in answers:
                    txt = str(rdata).strip('"')
                    if txt.startswith("v=spf1"):
                        spf_record = txt
                        break
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                pass

            dmarc_record = None
            try:
                answers = resolver.resolve(f"_dmarc.{validated_domain}", "TXT")
                for rdata in answers:
                    txt = str(rdata).strip('"')
                    if txt.startswith("v=DMARC1"):
                        dmarc_record = txt
                        break
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                pass

            duration_ms = int((time.time() - start_time) * 1000)

            score = 0
            issues = []

            if spf_record:
                score += 7
            else:
                issues.append("No SPF record found")

            if dmarc_record:
                score += 8
            else:
                issues.append("No DMARC record found")

            # DKIM requires knowing the selector, which we can't reliably guess.
            # We explicitly mark it as not tested rather than missing.

            if score == 15:
                status = "healthy"
                message = "Email security properly configured (SPF and DMARC)"
                recommendation = ""
            elif score > 0:
                status = "warning"
                message = f"Email security partially configured ({', '.join(issues)})"
                recommendation = (
                    "Configure both SPF and DMARC records to protect against spoofing."
                )
            else:
                status = "critical"
                message = "Email security not configured"
                recommendation = "Configure SPF, DKIM, and DMARC records to protect your domain's email reputation."

            return self._create_result(
                score=score,
                status=status,
                message=message,
                recommendation=recommendation,
                duration_ms=duration_ms,
                spf_record=spf_record,
                dmarc_record=dmarc_record,
                dkim_status="not_tested",  # Explicitly state DKIM cannot be verified without selector
                issues=issues,
            )

        except DomainValidationError as e:
            return self._create_result(
                score=0,
                status="critical",
                message=str(e),
                recommendation="Provide a valid, accessible public domain.",
            )
        except Exception as e:
            logger.error(f"Email security scan error for {domain}: {e}")
            return self._create_result(
                score=0,
                status="critical",
                message="Email security scan failed",
                recommendation="Check your domain's DNS configuration.",
            )


email_security_scanner = EmailSecurityScanner()
