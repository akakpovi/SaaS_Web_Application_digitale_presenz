"""Lighthouse performance & technical SEO scanner adapter.

Lighthouse is delegated to a resource-bounded sandbox (see
:mod:`scanners.executors.sandbox`): a one-shot hardened container when
``SCANNER_SANDBOX_MODE=docker``, otherwise a child process with CPU/RAM/time
limits.  The raw JSON report is normalised into:

* one :class:`~scanners.base.ScanResult` that the orchestrator stores as the
  ``performance`` CheckResult (score scaled to the category weight, 0–15);
* granular :class:`~scanners.base.NormalizedFinding` objects for every
  actionable performance/SEO audit, which AKA IA consumes later.

``execute()`` is overridden so the (expensive) Chromium run happens exactly
once and produces both artefacts.
"""

from __future__ import annotations

import logging
import re
import shutil
import time
from typing import Any

from django.conf import settings

from scanners.base import (
    BaseScanner,
    FindingStatus,
    NormalizedFinding,
    ScanContext,
    ScanOutcome,
    ScanResult,
    ScannerType,
    Severity,
)
from scanners.exceptions import TargetValidationError
from scanners.executors.command import CommandResult
from scanners.executors.sandbox import (
    SandboxError,
    SandboxMode,
    get_sandbox_executor,
)
from scanners.parsers.lighthouse import (
    CATEGORY_LABELS,
    METRIC_THRESHOLDS,
    LighthouseAudit,
    LighthouseReport,
    parse_lighthouse_json,
)
from scanners.security.target_validator import validate_target

logger = logging.getLogger(__name__)


#: Weight of the ``performance`` category in scans.services.scoring.
_PERFORMANCE_WEIGHT = 15

#: Lighthouse score thresholds (0–1).
_SCORE_HEALTHY = 0.90
_SCORE_WARNING = 0.50

_SEVERITY_RANK: dict[str, int] = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_WHITESPACE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _clean_text(value: str, limit: int = 1200) -> str:
    """Strip Lighthouse markdown links and normalise whitespace."""
    text = _MARKDOWN_LINK.sub(r"\1", value or "")
    text = _WHITESPACE.sub(" ", text).strip()
    return text[:limit]


def _severity_from_score(score: float | None) -> str:
    if score is None:
        return Severity.INFO
    if score >= 1.0:
        return Severity.INFO
    if score >= _SCORE_HEALTHY:
        return Severity.LOW
    if score >= _SCORE_WARNING:
        return Severity.MEDIUM
    return Severity.HIGH


def _status_from_severity(severity: str) -> str:
    if severity in (Severity.HIGH, Severity.CRITICAL):
        return FindingStatus.FAIL
    if severity in (Severity.MEDIUM, Severity.LOW):
        return FindingStatus.WARNING
    return FindingStatus.PASS


def _severity_from_threshold(audit_id: str, value: float | None) -> str | None:
    """Grade a metric against Core Web Vitals-style thresholds."""
    thresholds = METRIC_THRESHOLDS.get(audit_id)
    if thresholds is None or value is None:
        return None
    good_max, poor_min, _unit, _expected = thresholds
    if value <= good_max:
        return Severity.INFO
    if value <= poor_min:
        return Severity.MEDIUM
    return Severity.HIGH


def _worst_severity(first: str, second: str | None) -> str:
    if second is None:
        return first
    return first if _SEVERITY_RANK.get(first, 0) >= _SEVERITY_RANK.get(second, 0) else second


class LighthouseScanner(BaseScanner):
    """Lighthouse performance + technical SEO scanner."""

    name = "lighthouse"
    scanner_type = ScannerType.CLI
    _binary = "lighthouse"
    #: Lighthouse feeds the existing performance health category.
    check_result_category = "performance"
    scanner_version = "1.0"

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @property
    def _cfg(self) -> dict[str, Any]:
        return getattr(settings, "SCANNER_CONFIG", {}).get("lighthouse", {}) or {}

    @property
    def binary(self) -> str:
        return str(self._cfg.get("binary") or self._binary)

    @property
    def categories(self) -> tuple[str, ...]:
        configured = self._cfg.get("categories") or ("performance", "seo")
        if isinstance(configured, str):
            configured = [item.strip() for item in configured.split(",") if item.strip()]
        return tuple(configured) or ("performance", "seo")

    @property
    def timeout(self) -> int:  # type: ignore[override]
        return int(self._cfg.get("timeout", 120))

    def is_available(self) -> bool:
        executor = get_sandbox_executor()
        if executor.mode == SandboxMode.DOCKER:
            return executor.is_available(self.name, binary=self.binary)
        return shutil.which(self.binary) is not None

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def scan(self, domain: str) -> ScanResult:
        return self.execute(domain).result

    def execute(
        self,
        domain: str,
        context: ScanContext | None = None,
    ) -> ScanOutcome:
        """Run Lighthouse once and return the CheckResult + findings."""
        target = context.target if context is not None and context.target else None
        if target is None:
            try:
                target = validate_target(f"https://{domain}")
            except TargetValidationError as exc:
                return self._blocked_outcome(str(exc))

        if not self.is_available():
            return self._unavailable_outcome()

        timeout = (
            context.effective_timeout(self.timeout)
            if context is not None
            else self.timeout
        )

        executor = get_sandbox_executor()
        limits = (
            context.sandbox_limits
            if context is not None and context.sandbox_limits is not None
            else executor.limits_for(self.name, timeout=timeout)
        )
        command = self.build_command(target.url, {"target": target})

        env_extra: dict[str, str] = {}
        chrome_path = str(self._cfg.get("chrome_path") or "").strip()
        if chrome_path:
            env_extra["CHROME_PATH"] = chrome_path

        started = time.monotonic()
        try:
            command_result = executor.run(
                command,
                limits=limits,
                scanner_name=self.name,
                env_extra=env_extra or None,
            )
        except SandboxError as exc:
            logger.error("Lighthouse sandbox unavailable: %s", exc)
            return self._failure_outcome(
                code="lighthouse.sandbox_unavailable",
                message=f"Lighthouse could not be started safely: {exc}",
                title="Lighthouse sandbox unavailable",
                severity=Severity.MEDIUM,
                details={"error": str(exc)[:500]},
            )

        duration_ms = command_result.duration_ms or int(
            (time.monotonic() - started) * 1000
        )

        # ── Resource-limit failures are explicit, never silent ─────────
        if command_result.timed_out:
            return self._failure_outcome(
                code="lighthouse.timeout",
                message=(
                    f"Lighthouse exceeded its {limits.timeout_s}s budget — "
                    "performance/SEO score unavailable"
                ),
                title=f"Lighthouse timed out after {limits.timeout_s}s",
                severity=Severity.MEDIUM,
                duration_ms=duration_ms,
                details={
                    "timeout_s": limits.timeout_s,
                    "stderr": command_result.stderr[-1000:],
                },
            )

        if command_result.memory_exceeded:
            return self._failure_outcome(
                code="lighthouse.memory_limit",
                message=(
                    "Lighthouse was stopped because it exceeded its memory "
                    f"envelope ({limits.memory_mb} MB)"
                ),
                title="Lighthouse exceeded the memory limit",
                severity=Severity.MEDIUM,
                duration_ms=duration_ms,
                details={"memory_mb": limits.memory_mb},
            )

        if not command_result.stdout.strip():
            return self._failure_outcome(
                code="lighthouse.no_output",
                message=(
                    "Lighthouse produced no report "
                    f"(exit code {command_result.exit_code})"
                ),
                title="Lighthouse produced no report",
                severity=Severity.MEDIUM,
                duration_ms=duration_ms,
                details={
                    "exit_code": command_result.exit_code,
                    "stderr": command_result.stderr[-1000:],
                },
            )

        report = parse_lighthouse_json(command_result.stdout, self.categories)
        if report is None:
            return self._failure_outcome(
                code="lighthouse.parse_error",
                message="Lighthouse returned an unparseable JSON report",
                title="Lighthouse report could not be parsed",
                severity=Severity.MEDIUM,
                duration_ms=duration_ms,
                details={
                    "exit_code": command_result.exit_code,
                    "stdout_sample": command_result.stdout[:500],
                    "stderr": command_result.stderr[-1000:],
                },
            )

        # ── Post-run redirect guard ────────────────────────────────────
        # Lighthouse/Chromium follows redirects on its own; a target that
        # redirects to an internal service must not have its data stored.
        if report.final_url:
            try:
                validate_target(report.final_url)
            except TargetValidationError as exc:
                return self._blocked_outcome(
                    f"Lighthouse ended on a prohibited URL ({report.final_url}): {exc}",
                    duration_ms=duration_ms,
                )

        if report.runtime_error:
            code = report.runtime_error.get("code") or "runtime_error"
            message = report.runtime_error.get("message") or "unknown error"
            return self._failure_outcome(
                code="lighthouse.runtime_error",
                message=f"Lighthouse failed to audit the page: {message}",
                title=f"Lighthouse runtime error ({code})",
                severity=Severity.HIGH,
                duration_ms=duration_ms,
                details={
                    "runtime_error": report.runtime_error,
                    "run_warnings": report.run_warnings[:10],
                },
            )

        if not report.category_scores:
            return self._failure_outcome(
                code="lighthouse.no_scores",
                message="Lighthouse returned a report without any category score",
                title="Lighthouse report contains no scores",
                severity=Severity.MEDIUM,
                duration_ms=duration_ms,
                details={
                    "run_warnings": report.run_warnings[:10],
                    "final_url": report.final_url,
                },
            )

        findings = self.normalize(report, duration_ms=duration_ms)
        result = self._build_result(report, duration_ms=duration_ms)

        logger.info(
            "Lighthouse audit finished for %s: perf=%s seo=%s in %dms",
            target.hostname,
            report.percent_of("performance"),
            report.percent_of("seo"),
            duration_ms,
        )
        return ScanOutcome(result=result, findings=findings)

    def build_command(self, target: str, options: dict | None = None) -> list[str]:
        """Build the Lighthouse argv (target is always a separate argument)."""
        options = options or {}
        categories = ",".join(self.categories)

        command = [
            self.binary,
            target,
            "--output=json",
            "--output-path=stdout",
            "--quiet",
            f"--only-categories={categories}",
        ]

        preset = str(self._cfg.get("preset") or "").strip()
        if preset:
            command.append(f"--preset={preset}")

        chrome_flags = str(self._cfg.get("chrome_flags") or "").strip()
        extra_flags: list[str] = []

        proxy = str(self._cfg.get("chrome_proxy") or "").strip()
        if proxy:
            extra_flags.append(f"--proxy-server={proxy}")

        target_info = options.get("target")
        if target_info is not None and bool(self._cfg.get("pin_target_ip", True)):
            # Pin the audited hostname to the IP validated by the central SSRF
            # gate: Chromium then cannot be rebound to a private address.
            ipv4 = next(
                (ip for ip in getattr(target_info, "safe_ips", []) if ":" not in ip),
                None,
            )
            if ipv4:
                extra_flags.append(
                    f"--host-resolver-rules=MAP {target_info.hostname} {ipv4}"
                )

        if extra_flags:
            chrome_flags = " ".join(filter(None, [chrome_flags, *extra_flags]))

        if chrome_flags:
            command.append(f"--chrome-flags={chrome_flags}")

        return command

    def parse(self, output: str) -> LighthouseReport | None:
        return parse_lighthouse_json(output, self.categories)

    def scan_findings(
        self,
        domain: str,
        result: ScanResult | None = None,
    ) -> list[NormalizedFinding]:
        """Legacy entry point; reuses the single-run :meth:`execute` path."""
        return self.execute(domain).findings

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    def normalize(
        self,
        report: LighthouseReport,
        *,
        duration_ms: int = 0,
    ) -> list[NormalizedFinding]:
        """Convert a parsed report into database-compatible findings."""
        findings: list[NormalizedFinding] = []

        for category in self.categories:
            if category not in report.category_scores:
                continue
            findings.append(
                self._category_finding(category, report, duration_ms)
            )

        audit_findings = [
            self._audit_to_finding(audit, report, duration_ms)
            for audit in report.audits
        ]
        audit_findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK.get(finding.severity, 0),
                finding.check_code,
            )
        )

        max_findings = max(1, int(self._cfg.get("max_findings", 60)))
        findings.extend(audit_findings[:max_findings])
        return findings

    def _category_finding(
        self,
        category: str,
        report: LighthouseReport,
        duration_ms: int,
    ) -> NormalizedFinding:
        raw_score = report.score_of(category)
        percent = report.percent_of(category)
        severity = _severity_from_score(raw_score)
        status = _status_from_severity(severity) if raw_score is not None else FindingStatus.UNKNOWN
        label = CATEGORY_LABELS.get(category, category.replace("-", " ").title())
        min_score = int(self._cfg.get("min_score", 90))

        if raw_score is None:
            if percent is None:
                title = f"Lighthouse {label}: not measured"
            else:
                title = f"Lighthouse {label} score: {percent}/100"
        else:
            title = f"Lighthouse {label} score: {percent}/100"

        return NormalizedFinding(
            check_code=f"lighthouse.{category.replace('-', '_')}_score",
            category="performance" if category == "performance" else category,
            severity=severity,
            status=status,
            title=title[:255],
            description=(
                f"Lighthouse measured the {label} category at "
                f"{percent if percent is not None else 'n/a'}/100."
            ),
            evidence={
                "category": category,
                "score": raw_score,
                "percent": percent,
                "expected_min": min_score,
                "lighthouse_version": report.lighthouse_version,
                "final_url": report.final_url,
                "core_metrics": report.core_metrics() if category == "performance" else {},
            },
            detected_value=percent,
            expected_value=f">= {min_score}",
            recommendation=(
                ""
                if status == FindingStatus.PASS
                else f"Review the failing {label} audits below and fix the highest-impact items first."
            ),
            duration_ms=duration_ms,
        )

    def _audit_to_finding(
        self,
        audit: LighthouseAudit,
        report: LighthouseReport,
        duration_ms: int,
    ) -> NormalizedFinding:
        severity = _severity_from_score(audit.score)
        severity = _worst_severity(
            severity,
            _severity_from_threshold(audit.audit_id, audit.numeric_value),
        )

        if audit.score is None:
            status = FindingStatus.UNKNOWN
        else:
            status = _status_from_severity(severity)

        thresholds = METRIC_THRESHOLDS.get(audit.audit_id)
        expected_value = thresholds[3] if thresholds else None

        description = _clean_text(audit.description, 1500)
        recommendation = ""
        if status in (FindingStatus.FAIL, FindingStatus.WARNING):
            recommendation = (
                f"Fix the Lighthouse audit '{audit.title}': {description}"
            )[:2000]

        return NormalizedFinding(
            check_code=f"lighthouse.{audit.audit_id}"[:128],
            category=(
                "performance" if audit.category == "performance" else audit.category
            )[:32],
            severity=severity,
            status=status,
            title=audit.title[:255],
            description=description,
            evidence={
                "audit_id": audit.audit_id,
                "category": audit.category,
                "score": audit.score,
                "score_display_mode": audit.score_display_mode,
                "display_value": audit.display_value,
                "numeric_value": audit.numeric_value,
                "numeric_unit": audit.numeric_unit,
                "weight": audit.weight,
                "lighthouse_version": report.lighthouse_version,
            },
            detected_value=(
                audit.numeric_value
                if audit.numeric_value is not None
                else (audit.display_value or audit.score)
            ),
            expected_value=expected_value,
            recommendation=recommendation,
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------
    # Result builders
    # ------------------------------------------------------------------

    def _build_result(
        self,
        report: LighthouseReport,
        *,
        duration_ms: int,
    ) -> ScanResult:
        performance = report.score_of("performance")
        performance_percent = report.percent_of("performance")
        seo_percent = report.percent_of("seo")
        performance_weight = self._performance_weight()

        if performance is None:
            score = 0
            status = "warning"
            message = "Lighthouse returned no performance score"
        else:
            score = int(
                round(max(0.0, min(1.0, performance)) * performance_weight)
            )
            if performance >= _SCORE_HEALTHY:
                status = "healthy"
            elif performance >= _SCORE_WARNING:
                status = "warning"
            else:
                status = "critical"

        metrics = report.core_metrics()
        metric_parts = []
        for audit_id, label in (
            ("largest-contentful-paint", "LCP"),
            ("cumulative-layout-shift", "CLS"),
            ("total-blocking-time", "TBT"),
            ("first-contentful-paint", "FCP"),
        ):
            display = metrics.get(audit_id, {}).get("display")
            if display:
                metric_parts.append(f"{label} {display}")

        message = (
            f"Lighthouse performance {performance_percent if performance_percent is not None else 'n/a'}/100, "
            f"SEO {seo_percent if seo_percent is not None else 'n/a'}/100"
        )
        if metric_parts:
            message += " (" + ", ".join(metric_parts) + ")"

        failing = report.failed_audits()
        recommendation = ""
        if failing:
            top_titles = "; ".join(audit.title for audit in failing[:3])
            recommendation = (
                f"Priority fixes: {top_titles}. "
                "See the Lighthouse findings for the full audit list."
            )[:2000]

        details = {
            "lighthouse_version": report.lighthouse_version,
            "requested_url": report.requested_url,
            "final_url": report.final_url,
            "fetch_time": report.fetch_time,
            "category_scores": {
                category: report.percent_of(category)
                for category in report.category_scores
            },
            "core_metrics": metrics,
            "failed_audits": len(failing),
            "run_warnings": report.run_warnings[:10],
        }

        return ScanResult(
            score=score,
            status=status,
            message=message[:2000],
            details=details,
            recommendation=recommendation,
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------
    # Failure outcomes
    # ------------------------------------------------------------------

    @staticmethod
    def _performance_weight() -> int:
        """Read the current weight of the ``performance`` category.

        Kept in sync with ``scans.services.scoring`` so a future re-balancing
        of the health score cannot make Lighthouse emit an out-of-range score.
        """
        try:
            from scans.services.scoring import CHECK_WEIGHTS

            return int(CHECK_WEIGHTS.get("performance", _PERFORMANCE_WEIGHT))
        except Exception:  # pragma: no cover - settings/import defensive path
            return _PERFORMANCE_WEIGHT

    def _failure_outcome(
        self,
        *,
        code: str,
        message: str,
        title: str,
        severity: str,
        details: dict[str, Any] | None = None,
        duration_ms: int = 0,
    ) -> ScanOutcome:
        """Build a scored failure: missing data must not look healthy."""
        finding = NormalizedFinding(
            check_code=code[:128],
            category="performance",
            severity=severity,
            status=FindingStatus.FAIL if severity in (Severity.HIGH, Severity.CRITICAL) else FindingStatus.WARNING,
            title=title[:255],
            description=message[:2000],
            evidence=details or {},
            duration_ms=duration_ms,
        )
        result = ScanResult(
            score=0,
            status="warning",
            message=message[:2000],
            details=details or {},
            recommendation="Check that the site is publicly reachable and that Lighthouse/Chromium is installed.",
            duration_ms=duration_ms,
        )
        return ScanOutcome(result=result, findings=[finding])

    def _blocked_outcome(
        self,
        reason: str,
        *,
        duration_ms: int = 0,
    ) -> ScanOutcome:
        finding = NormalizedFinding(
            check_code="lighthouse.target_validation",
            category="performance",
            severity=Severity.HIGH,
            status=FindingStatus.FAIL,
            title="Target validation failed",
            description=reason[:2000],
            duration_ms=duration_ms,
        )
        result = ScanResult(
            score=None,
            status="critical",
            message=f"SSRF protection blocked the Lighthouse target: {reason}"[:2000],
            details={"blocked": True, "reason": reason[:500]},
            recommendation="Provide a valid, publicly resolvable domain.",
            duration_ms=duration_ms,
        )
        return ScanOutcome(result=result, findings=[finding])

    def _unavailable_outcome(self) -> ScanOutcome:
        finding = NormalizedFinding(
            check_code="lighthouse.unavailable",
            category="performance",
            severity=Severity.INFO,
            status=FindingStatus.NOT_APPLICABLE,
            title="Lighthouse not available",
            description=(
                "The Lighthouse binary is not installed on the worker "
                "(or no Docker image is configured for it)."
            ),
            recommendation=(
                "Build the worker image with INSTALL_LIGHTHOUSE=true, or "
                "configure SCANNER_SANDBOX docker mode for lighthouse."
            ),
        )
        result = ScanResult(
            score=None,
            status="neutral",
            message="Lighthouse not available — skipped",
            details={"available": False},
            recommendation="Install Lighthouse/Chromium or configure a Docker image.",
        )
        return ScanOutcome(result=result, findings=[finding])


lighthouse_scanner = LighthouseScanner()
