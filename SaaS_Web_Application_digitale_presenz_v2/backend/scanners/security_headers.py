"""Security headers scanner."""

import logging

from core.security import DomainValidationError, safe_request
from .base import BaseScanner, ScanResult

logger = logging.getLogger(__name__)


class SecurityHeadersScanner(BaseScanner):
    """Check security headers."""

    name = "security_headers"
    timeout = 15

    REQUIRED_HEADERS = {
        "Strict-Transport-Security": 3,
        "X-Content-Type-Options": 3,
        "X-Frame-Options": 3,
        "Content-Security-Policy": 3,
        "Referrer-Policy": 3,
    }

    def scan(self, domain: str) -> ScanResult:
        """Scan security headers."""
        try:
            url = f"https://{domain}"
            response = safe_request(
                url,
                method="HEAD",
                connect_timeout=5.0,
                read_timeout=float(self.timeout),
                stream_body=False,
            )

            score = 0
            present_headers = {}
            missing_headers = []

            # Use case-insensitive header lookup provided by requests
            headers = response.headers

            for header, points in self.REQUIRED_HEADERS.items():
                if header in headers or header.lower() in headers:
                    score += points
                    # requests.structures.CaseInsensitiveDict correctly handles this
                    present_headers[header] = headers.get(header) or headers.get(
                        header.lower()
                    )
                else:
                    # Special fallback: if Permissions-Policy is present instead of Referrer-Policy, give points
                    if header == "Referrer-Policy" and (
                        "Permissions-Policy" in headers
                        or "permissions-policy" in headers
                    ):
                        score += points
                        present_headers["Permissions-Policy"] = headers.get(
                            "Permissions-Policy"
                        ) or headers.get("permissions-policy")
                    else:
                        missing_headers.append(header)

            if score >= 12:
                status = "healthy"
                message = f"Good security headers ({score}/15)"
                recommendation = ""
            elif score >= 6:
                status = "warning"
                message = f"Some security headers missing ({score}/15)"
                recommendation = (
                    f"Consider adding the missing headers: {', '.join(missing_headers)}"
                )
            else:
                status = "critical"
                message = f"Poor security headers ({score}/15)"
                recommendation = f"Add critical security headers to prevent common vulnerabilities: {', '.join(missing_headers)}"

            return self._create_result(
                score=score,
                status=status,
                message=message,
                recommendation=recommendation,
                duration_ms=response.elapsed_ms,
                present_headers=present_headers,
                missing_headers=missing_headers,
            )

        except DomainValidationError as e:
            return self._create_result(
                score=0,
                status="critical",
                message=str(e),
                recommendation="Provide a valid, accessible public domain.",
            )
        except Exception as e:
            logger.error(f"Security headers scan error for {domain}: {e}")
            return self._create_result(
                score=0,
                status="critical",
                message="Security headers scan failed",
                recommendation="Ensure the server is accessible and responding to HEAD requests.",
            )


security_headers_scanner = SecurityHeadersScanner()
