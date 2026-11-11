"""SSL certificate scanner."""

import logging
import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Any

from core.security import (
    DomainValidationError,
    SSRFBlockedError,
    _resolve_and_validate,
    validate_domain_for_scan,
)
from .base import BaseScanner, ScanResult

logger = logging.getLogger(__name__)


class SSLScanner(BaseScanner):
    """Check SSL certificate validity and expiration."""

    name = "ssl"
    timeout = 10

    def scan(self, domain: str) -> ScanResult:
        """Scan SSL certificate."""
        start_time = time.time()
        try:
            validated_domain = validate_domain_for_scan(domain)
            safe_ips = _resolve_and_validate(validated_domain)
            target_ip = safe_ips[0]

            context = ssl.create_default_context()
            # Connect to the safe IP, but verify the hostname (SNI)
            with socket.create_connection(
                (target_ip, 443), timeout=self.timeout
            ) as sock:
                with context.wrap_socket(
                    sock, server_hostname=validated_domain
                ) as ssock:
                    cert = ssock.getpeercert()

            not_after = cert["notAfter"]
            expiry_date = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)

            days_until_expiry = (expiry_date - datetime.now(timezone.utc)).days

            issuer = dict(x[0] for x in cert["issuer"])
            subject = dict(x[0] for x in cert["subject"])
            duration_ms = int((time.time() - start_time) * 1000)

            if days_until_expiry > 60:
                score = 20
                status = "healthy"
                message = f"SSL certificate valid for {days_until_expiry} days"
                recommendation = ""
            elif days_until_expiry > 30:
                score = 16
                status = "healthy"
                message = f"SSL certificate expires in {days_until_expiry} days"
                recommendation = "Plan to renew the SSL certificate soon."
            elif days_until_expiry > 7:
                score = 10
                status = "warning"
                message = f"SSL certificate expires soon ({days_until_expiry} days)"
                recommendation = "Renew the SSL certificate immediately."
            else:
                score = 4
                status = "critical"
                message = f"SSL certificate expires very soon or is expired ({days_until_expiry} days)"
                recommendation = (
                    "Renew the SSL certificate immediately to avoid outages."
                )

            return self._create_result(
                score=score,
                status=status,
                message=message,
                recommendation=recommendation,
                duration_ms=duration_ms,
                days_until_expiry=days_until_expiry,
                expiry_date=expiry_date.isoformat(),
                issuer=issuer.get("organizationName", "Unknown"),
                subject_cn=subject.get("commonName", validated_domain),
                version=cert.get("version", "Unknown"),
            )

        except (DomainValidationError, SSRFBlockedError) as e:
            return self._create_result(
                score=0,
                status="critical",
                message=str(e),
                recommendation="Provide a valid, accessible public domain.",
            )
        except ssl.SSLError as e:
            return self._create_result(
                score=0,
                status="critical",
                message="SSL certificate error or invalid chain",
                recommendation="Ensure a valid SSL certificate is installed and properly configured.",
            )
        except socket.timeout:
            return self._create_result(
                score=0,
                status="critical",
                message=f"SSL check timeout (>{self.timeout}s)",
                recommendation="Ensure the server is accessible on port 443.",
            )
        except Exception as e:
            logger.error(f"SSL scan error for {domain}: {e}")
            return self._create_result(
                score=0,
                status="critical",
                message="SSL scan failed",
                recommendation="Ensure the server is running and accessible.",
            )


ssl_scanner = SSLScanner()
