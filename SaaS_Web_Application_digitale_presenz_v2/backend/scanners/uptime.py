"""Uptime scanner."""

import logging

from core.security import DomainValidationError, safe_request
from .base import BaseScanner, ScanResult

logger = logging.getLogger(__name__)


class UptimeScanner(BaseScanner):
    """Check whether a website is currently reachable."""

    name = "uptime"
    timeout = 10

    def scan(self, domain: str) -> ScanResult:
        """Check the current availability of the website."""

        try:
            response = safe_request(
                f"https://{domain}",
                method="HEAD",
                connect_timeout=5.0,
                read_timeout=float(self.timeout),
                stream_body=False,
            )

            if response.status_code < 500:
                return self._create_result(
                    score=None,
                    status="healthy",
                    message="Website is currently online",
                    duration_ms=response.elapsed_ms,
                    current_status="up",
                    status_code=response.status_code,
                )

            return self._create_result(
                score=None,
                status="critical",
                message=(f"Website returned a server error ({response.status_code})"),
                recommendation=(
                    "Investigate server logs to determine the cause of the downtime."
                ),
                duration_ms=response.elapsed_ms,
                current_status="down",
                status_code=response.status_code,
            )

        except DomainValidationError:
            logger.warning(
                "uptime_check_failed",
                extra={"domain": domain},
            )

            return self._create_result(
                score=None,
                status="critical",
                message="Website could not be reached safely.",
                recommendation=(
                    "Ensure the domain resolves publicly and the website is reachable."
                ),
                current_status="down",
            )

        except Exception:
            logger.exception(
                "uptime_scan_error",
                extra={"domain": domain},
            )

            return self._create_result(
                score=None,
                status="critical",
                message="Website is currently offline",
                recommendation=(
                    "Ensure the server is running and reachable from the internet."
                ),
                current_status="down",
            )


uptime_scanner = UptimeScanner()
