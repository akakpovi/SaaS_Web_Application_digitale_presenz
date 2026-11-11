"""Performance scanner."""

import logging

from core.security import DomainValidationError, safe_request
from .base import BaseScanner, ScanResult

logger = logging.getLogger(__name__)


class PerformanceScanner(BaseScanner):
    """Check website performance."""

    name = "performance"
    timeout = 15

    def scan(self, domain: str) -> ScanResult:
        """Scan website performance."""
        try:
            url = f"https://{domain}"
            response = safe_request(
                url,
                method="GET",
                connect_timeout=5.0,
                read_timeout=float(self.timeout),
                max_bytes=5 * 1024 * 1024,
            )

            load_time_ms = response.elapsed_ms
            page_size_kb = len(response.body) / 1024
            has_compression = (
                "gzip" in response.headers.get("Content-Encoding", "").lower()
            )

            score = 15
            recommendations = []

            if load_time_ms > 3000:
                score -= 6
                recommendations.append("Reduce server response time.")
            elif load_time_ms > 1000:
                score -= 3
                recommendations.append("Consider optimizing TTFB (Time to First Byte).")

            if page_size_kb > 2000:
                score -= 5
                recommendations.append("Reduce page size (currently > 2MB).")
            elif page_size_kb > 1000:
                score -= 2
                recommendations.append("Optimize assets to reduce page size.")

            if not has_compression and page_size_kb > 50:
                score -= 2
                recommendations.append("Enable GZIP or Brotli compression.")

            score = max(0, score)

            if score >= 12:
                status = "healthy"
                message = f"Good performance ({load_time_ms}ms load time)"
            elif score >= 8:
                status = "warning"
                message = f"Average performance ({load_time_ms}ms load time)"
            else:
                status = "critical"
                message = f"Poor performance ({load_time_ms}ms load time)"

            return self._create_result(
                score=score,
                status=status,
                message=message,
                recommendation=" ".join(recommendations),
                duration_ms=response.elapsed_ms,
                load_time_ms=load_time_ms,
                page_size_kb=round(page_size_kb, 2),
                has_compression=has_compression,
            )

        except DomainValidationError as e:
            return self._create_result(
                score=0,
                status="critical",
                message=str(e),
                recommendation="Provide a valid, accessible public domain.",
            )
        except Exception as e:
            logger.error(f"Performance scan error for {domain}: {e}")
            return self._create_result(
                score=0,
                status="critical",
                message="Performance scan failed",
                recommendation="Ensure the server is accessible and responding in a timely manner.",
            )


performance_scanner = PerformanceScanner()
