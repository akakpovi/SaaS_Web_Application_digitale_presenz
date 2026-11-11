"""Website availability scanner."""

import logging
from typing import Any

from core.security import DomainValidationError, safe_request
from .base import BaseScanner, ScanResult

logger = logging.getLogger(__name__)


class WebsiteScanner(BaseScanner):
    """Check website availability and HTTP status."""

    name = "website"
    timeout = 15

    def scan(self, domain: str) -> ScanResult:
        """Scan website availability."""
        try:
            url = f"https://{domain}"
            response = safe_request(
                url, method="GET", connect_timeout=5.0, read_timeout=float(self.timeout)
            )

            if response.status_code == 200:
                return self._create_result(
                    score=20,
                    status="healthy",
                    message="Website is accessible",
                    recommendation="",
                    duration_ms=response.elapsed_ms,
                    status_code=response.status_code,
                    final_url=response.url,
                    redirect_count=len(response.redirect_chain),
                )
            elif 200 <= response.status_code < 300:
                return self._create_result(
                    score=18,
                    status="healthy",
                    message=f"Website accessible (HTTP {response.status_code})",
                    recommendation="Ensure the primary endpoint returns 200 OK.",
                    duration_ms=response.elapsed_ms,
                    status_code=response.status_code,
                )
            elif 300 <= response.status_code < 400:
                # safe_request follows redirects, so a final 3xx means it didn't resolve to a 2xx,
                # or it exceeded MAX_REDIRECTS.
                return self._create_result(
                    score=14,
                    status="warning",
                    message=f"Website redirects or loops (HTTP {response.status_code})",
                    recommendation="Fix redirect chains to resolve to a 200 OK.",
                    duration_ms=response.elapsed_ms,
                    status_code=response.status_code,
                    redirect_count=len(response.redirect_chain),
                )
            else:
                return self._create_result(
                    score=0,
                    status="critical",
                    message=f"Website returned error (HTTP {response.status_code})",
                    recommendation="Check the server logs and ensure the application is running.",
                    duration_ms=response.elapsed_ms,
                    status_code=response.status_code,
                )

        except DomainValidationError as e:
            return self._create_result(
                score=0,
                status="critical",
                message=str(e),
                recommendation="Provide a valid, accessible public domain.",
            )
        except Exception as e:
            logger.error(f"Unexpected error scanning {domain}: {e}")
            return self._create_result(
                score=0,
                status="critical",
                message="Cannot connect to website",
                recommendation="Ensure the domain resolves and the server is running.",
            )


website_scanner = WebsiteScanner()
