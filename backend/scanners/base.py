"""Base classes and result types for website scanners."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Standardized scanner result.

    Weighted categories return an integer score capped by their category weight.
    Non-weighted categories such as uptime return ``None``.
    """

    score: int | None
    status: str
    message: str
    details: dict[str, Any]
    recommendation: str = ""
    duration_ms: int = 0
    checked_at: datetime = field(
        default_factory=timezone.now
    )


class BaseScanner(ABC):
    """Base class for all scanners."""

    name: str
    timeout: int = 30
    scanner_version: str = "1.0"

    @abstractmethod
    def scan(self, domain: str) -> ScanResult:
        """Run the scanner."""
        raise NotImplementedError

    def _create_result(
        self,
        score: int | None,
        status: str,
        message: str,
        recommendation: str = "",
        duration_ms: int = 0,
        **details: Any,
    ) -> ScanResult:
        """Create a standardized scanner result."""

        return ScanResult(
            score=score,
            status=status,
            message=message,
            recommendation=recommendation,
            duration_ms=duration_ms,
            details=details,
        )