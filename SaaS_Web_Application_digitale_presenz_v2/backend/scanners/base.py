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

import inspect
import logging
import shutil
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final, Sequence

from django.utils import timezone


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class ScannerType:
    """Scanner type constants."""

    INTERNAL = "internal"  # Pure-Python checker (no external binary)
    CLI = "cli"  # External command-line tool
    API = "api"  # External tool via API (e.g. ZAP REST)


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
# Explicit scanner-status mappings
#
# Declared exhaustively (and at module level) so that an unmapped scanner
# status is surfaced through ``logger.warning`` instead of being silently
# swallowed by a ``dict.get()`` default.  ``Severity.UNKNOWN`` does not exist
# — referencing it used to raise ``AttributeError`` and abort the whole
# scanner pipeline before any CheckResult / Finding was written.
# ---------------------------------------------------------------------------

SEVERITY_BY_SCANNER_STATUS: Final[dict[str, str]] = {
    "healthy": Severity.INFO,
    "passed": Severity.INFO,
    "good": Severity.INFO,
    "online": Severity.INFO,
    "neutral": Severity.INFO,
    "unknown": Severity.INFO,
    "warning": Severity.MEDIUM,
    "failed": Severity.HIGH,
    "error": Severity.HIGH,
    "critical": Severity.HIGH,
    "offline": Severity.CRITICAL,
    "down": Severity.CRITICAL,
}

FINDING_STATUS_BY_SCANNER_STATUS: Final[dict[str, str]] = {
    "healthy": FindingStatus.PASS,
    "passed": FindingStatus.PASS,
    "good": FindingStatus.PASS,
    "online": FindingStatus.PASS,
    "neutral": FindingStatus.UNKNOWN,
    "unknown": FindingStatus.UNKNOWN,
    "warning": FindingStatus.WARNING,
    "failed": FindingStatus.FAIL,
    "error": FindingStatus.FAIL,
    "critical": FindingStatus.FAIL,
    "offline": FindingStatus.FAIL,
    "down": FindingStatus.FAIL,
}

#: Used only when a scanner reports a status outside the maps above.
_FALLBACK_SEVERITY: Final[str] = Severity.MEDIUM
_FALLBACK_FINDING_STATUS: Final[str] = FindingStatus.UNKNOWN


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


@dataclass(frozen=True)
class ScanContext:
    """Per-step execution contract passed from the orchestrator to scanners.

    It carries the central SSRF validation result and the remaining scan
    budget so an external tool never runs longer than the scan allows.
    ``target`` is a ``scanners.security.target_validator.TargetInfo`` (typed
    loosely here to keep this module free of Django/security imports).
    """

    scan_id: int
    domain: str
    timeout: int
    """Effective per-step timeout in seconds, already clamped by the budget."""

    deadline_monotonic: float
    """``time.monotonic()`` deadline shared by the whole scan."""

    target: Any = None
    """Validated target (``TargetInfo``) for external scanners, else ``None``."""

    sandbox_limits: Any = None
    """``SandboxLimits`` computed by the orchestrator for delegated tools."""

    profile: str | None = None
    """Trusted scanner profile selected by the scan step, if any.

    Only the orchestrator supplies this value; it never comes from request
    data.  Adapters without profiles ignore it.
    """

    def remaining_seconds(self) -> float:
        """Seconds left in the overall scan budget (never negative)."""
        return max(0.0, self.deadline_monotonic - time.monotonic())

    def effective_timeout(self, default: int) -> int:
        """Clamp *default* to the remaining scan budget (minimum 1s)."""
        remaining = self.remaining_seconds()
        if remaining <= 0:
            return 1
        return max(1, min(int(default), int(remaining)))


@dataclass
class ScanOutcome:
    """Both artefacts produced by a single scanner execution.

    External CLI tools are expensive (a Lighthouse/Chromium run is 10–60 s),
    so ``scan()`` and ``scan_findings()`` must never run the tool twice.  A
    scanner that overrides :meth:`BaseScanner.execute` returns this object
    and the orchestrator persists both halves without re-execution.
    """

    result: ScanResult
    findings: list[NormalizedFinding] = field(default_factory=list)
    #: Raw scanner output, kept out of ``ScanResult.details`` so it is never
    #: persisted in a CheckResult or exposed through an API.  The orchestrator
    #: archives it privately and redacts it before writing.
    raw_report: str | None = None
    raw_report_format: str = ""
    raw_report_meta: dict[str, Any] = field(default_factory=dict)


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

    requires_advanced_security: bool = False
    """Opt-in tools (ZAP, Nuclei) that must not run without the global flag.

    The orchestrator skips their step when
    ``SCANNER_ADVANCED_SECURITY_ENABLED`` is false; the adapters also refuse
    to execute when called directly.
    """

    check_result_category: str | None = None
    """Explicit ``CheckResult.Category`` produced by this scanner.

    When set, the orchestrator uses it instead of its legacy name→category
    map.  Scanners that do not contribute to the health score (nmap, nikto,
    …) leave it ``None`` and are ignored by the CheckResult bridge.
    """

    _findings_signature_cache: dict[type, bool] = {}

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

        # In Docker mode availability is "image configured and Docker present",
        # not "binary on the worker's PATH".
        if self.scanner_type == ScannerType.CLI:
            from scanners.executors.sandbox import SandboxMode, get_sandbox_executor

            executor = get_sandbox_executor()
            if executor.mode == SandboxMode.DOCKER:
                return executor.is_available(self.name)

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

    def normalize(
        self, parsed_results: list[dict[str, Any]]
    ) -> list[NormalizedFinding]:
        """Convert parsed dicts to :class:`NormalizedFinding` instances."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement normalize()"
        )

    def execute(
        self,
        domain: str,
        context: ScanContext | None = None,
    ) -> ScanOutcome:
        """Execute the scanner once and return result + findings.

        The default implementation is backward compatible with every legacy
        adapter: it calls ``scan()`` and derives findings from that exact
        result.  External tools that need the raw command output to build
        findings (Lighthouse, testssl.sh) override this method so the binary
        runs exactly once.
        """
        result = self.scan(domain)
        return ScanOutcome(
            result=result,
            findings=self._collect_findings(domain, result),
        )

    def _findings_accepts_result(self) -> bool:
        """Return True when ``scan_findings`` accepts ``result=``."""
        key = type(self)
        cached = BaseScanner._findings_signature_cache.get(key)
        if cached is None:
            try:
                params = inspect.signature(self.scan_findings).parameters
                cached = "result" in params
            except (TypeError, ValueError):
                cached = False
            BaseScanner._findings_signature_cache[key] = cached
        return cached

    def _collect_findings(
        self,
        domain: str,
        result: ScanResult,
    ) -> list[NormalizedFinding]:
        if self._findings_accepts_result():
            return self.scan_findings(domain, result=result)
        return self.scan_findings(domain)

    def scan_findings(
        self,
        domain: str,
        result: ScanResult | None = None,
    ) -> list[NormalizedFinding]:
        """Run the scanner and return normalized findings.

        Default implementation converts a :class:`ScanResult` to a single
        :class:`NormalizedFinding`.

        ``result`` may be supplied by the orchestrator when ``scan()`` has
        already been executed for the same domain.  This avoids running the
        scanner twice (two HTTP/TLS/DNS round-trips) and guarantees the
        findings are derived from the exact ScanResult that was persisted as
        CheckResult.  When ``result`` is ``None`` the scanner is executed
        here, which keeps the historical single-argument call working.

        CLI scanners with separate parse/normalize steps override this
        method and manage their own execution lifecycle.
        """
        if result is None:
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
        # Explicit mapping — an unknown status is logged, never silent.
        status_key = (result.status or "").strip().lower()
        if status_key not in SEVERITY_BY_SCANNER_STATUS:
            logger.warning(
                "Scanner '%s' returned unmapped status %r for %s — falling "
                "back to severity=%s / finding_status=%s",
                self.name,
                result.status,
                domain,
                _FALLBACK_SEVERITY,
                _FALLBACK_FINDING_STATUS,
            )

        finding_status = FINDING_STATUS_BY_SCANNER_STATUS.get(
            status_key, _FALLBACK_FINDING_STATUS
        )
        severity = SEVERITY_BY_SCANNER_STATUS.get(status_key, _FALLBACK_SEVERITY)

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
