"""Base classes and result types for website scanners.

This module defines the shared contract that all scanners — both internal
Python checkers and external tool adapters — must implement.

Backward compatibility
----------------------
:class:`ScanResult` and :class:`BaseScanner` keep their original interface
so that the ``public_checker`` and other callers continue to work unchanged.

New additions
-------------
:class:`NormalizedFinding`
    A scanner-agnostic finding record that maps to the ``Finding`` DB model.
    The Score Engine operates on these, not on raw scanner output.

:class:`BaseScanner`
    Extended with ``scanner_type``, ``is_available()``, ``build_command()``,
    ``parse()``, and ``normalize()``.  The ``scan()`` method remains the
    primary entry point used by the orchestrator.
"""

from __future__ import annotations

import logging
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Sequence

from django.utils import timezone


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class ScannerType:
    """Scanner type constants."""
    INTERNAL = "internal"    # Pure-Python checker (no external binary)
    CLI = "cli"              # External command-line tool
    API = "api"              # External tool via API (e.g. ZAP REST)


class Severity:
    """Finding severity constants (maps to Finding.Severity choices)."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus:
    """Finding status constants (maps to Finding.Status choices)."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ScanResult:
    """Standardised scanner result (legacy, kept for backward compatibility).

    Weighted categories return an integer score capped by their category weight.
    Non-weighted categories such as uptime return ``None``.
    """

    score: int | None
    status: str
    message: str
    details: dict[str, Any]
    recommendation: str = ""
    duration_ms: int = 0
    checked_at: datetime = field(default_factory=timezone.now)


@dataclass
class NormalizedFinding:
    """Scanner-agnostic finding, independent of which tool produced it.

    This is the primary data structure flowing from scanners through to the
    ScoreEngine → CheckResult → global health score pipeline.

    The ``check_code`` must be unique per check across the whole system
    (e.g. ``ssl.certificate_valid``, ``headers.hsts``, ``dns.a_records``).
    """

    check_code: str
    """Dot-separated code, e.g. 'ssl.certificate_valid'."""

    category: str
    """Category matching CheckResult.Category choices."""

    severity: str
    """One of :class:`Severity` constants."""

    status: str
    """One of :class:`FindingStatus` constants."""

    title: str
    """Short, human-readable title."""

    description: str = ""
    """Detailed description of what was found."""

    evidence: dict[str, Any] = field(default_factory=dict)
    """Raw technical evidence (headers, cert details, DNS records, etc.)."""

    detected_value: Any = None
    """The value that was actually found (e.g. '180' for cert days)."""

    expected_value: Any = None
    """The value that was expected (e.g. '>= 30' for cert days)."""

    recommendation: str = ""
    """Human-readable remediation advice."""

    reference_url: str = ""
    """Link to documentation or CVE."""

    duration_ms: int = 0
    """Time taken to produce this finding."""


# ---------------------------------------------------------------------------
# Base scanner
# ---------------------------------------------------------------------------

class BaseScanner(ABC):
    """Base class for all scanners.

    Subclasses must set ``name`` and implement ``scan()``.  External tool
    adapters should also implement ``build_command()``, ``parse()``, and
    ``normalize()``.

    The orchestrator calls ``scan()`` and expects a :class:`ScanResult` for
    backward compat with the health score engine, and a list of
    :class:`NormalizedFinding` via ``scan_findings()``.
    """

    name: str = ""
    """Unique identifier used by the registry (e.g. 'nmap', 'ssl')."""

    timeout: int = 30
    """Default timeout in seconds.  Overridden by SCANNER_CONFIG."""

    scanner_version: str = "1.0"

    scanner_type: str = ScannerType.INTERNAL
    """Type of scanner — used by orchestrator for scheduling decisions."""

    # The binary name used by CLI scanners (e.g. 'nmap').
    # Internal scanners leave this as None.
    _binary: str | None = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if this scanner can run.

        Internal scanners are always available.  CLI scanners check that
        their binary exists on PATH.
        """
        if self.scanner_type == ScannerType.INTERNAL:
            return True
        if self._binary is None:
            return False
        return shutil.which(self._binary) is not None

    # ------------------------------------------------------------------
    # Core interface (mandatory)
    # ------------------------------------------------------------------

    @abstractmethod
    def scan(self, domain: str) -> ScanResult:
        """Run the scanner and return a :class:`ScanResult`.

        This is the primary entry point.  Implementations must catch all
        exceptions and return a result with status='critical' rather than
        raising.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Extended interface (optional for CLI scanners)
    # ------------------------------------------------------------------

    def build_command(self, target: str, options: dict | None = None) -> list[str]:
        """Return the command to run as a list of arguments.

        ``target`` is the pre-validated, SSRF-safe hostname or IP.

        CLI scanner subclasses must override this method.
        Internal scanners can leave it unimplemented.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement build_command()"
        )

    def parse(self, output: str) -> list[dict[str, Any]]:
        """Parse raw scanner output and return a list of raw finding dicts.

        Called after ``CommandExecutor.run()``.  The return value is passed
        to ``normalize()``.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement parse()"
        )

    def normalize(self, parsed_results: list[dict[str, Any]]) -> list[NormalizedFinding]:
        """Convert parsed dicts to :class:`NormalizedFinding` instances."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement normalize()"
        )

    def scan_findings(self, domain: str) -> list[NormalizedFinding]:
        """Run the scanner and return normalized findings.

        Default implementation calls ``scan()`` and converts the
        :class:`ScanResult` to a single :class:`NormalizedFinding`.
        CLI scanners with separate parse/normalize steps should override
        this.
        """
        result = self.scan(domain)
        return self._scan_result_to_findings(result, domain)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_result(
        self,
        score: int | None,
        status: str,
        message: str,
        recommendation: str = "",
        duration_ms: int = 0,
        **details: Any,
    ) -> ScanResult:
        """Create a standardised scanner result."""
        return ScanResult(
            score=score,
            status=status,
            message=message,
            recommendation=recommendation,
            duration_ms=duration_ms,
            details=details,
        )

    def _scan_result_to_findings(
        self, result: ScanResult, domain: str
    ) -> list[NormalizedFinding]:
        """Convert a :class:`ScanResult` to a single :class:`NormalizedFinding`.

        This default conversion is used by legacy scanners that return a
        single aggregated result.  Scanners that produce granular findings
        should override ``scan_findings()`` instead.
        """
        from scans.models import CheckResult

        # Map internal status strings to Finding statuses.
        status_map = {
            "healthy": FindingStatus.PASS,
            "warning": FindingStatus.WARNING,
            "critical": FindingStatus.FAIL,
            "neutral": FindingStatus.UNKNOWN,
        }
        # Map internal status to severity.
        severity_map = {
            "healthy": Severity.INFO,
            "warning": Severity.MEDIUM,
            "critical": Severity.HIGH,
            "neutral": Severity.INFO,
        }

        finding_status = status_map.get(result.status, FindingStatus.UNKNOWN)
        severity = severity_map.get(result.status, Severity.MEDIUM)

        # Derive category from scanner name.
        category = self.name
        check_code = f"{self.name}.overall"

        return [
            NormalizedFinding(
                check_code=check_code,
                category=category,
                severity=severity,
                status=finding_status,
                title=result.message,
                description=result.message,
                evidence=result.details,
                recommendation=result.recommendation,
                duration_ms=result.duration_ms,
            )
        ]