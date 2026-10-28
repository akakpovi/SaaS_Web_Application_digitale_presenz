"""Nuclei template-based vulnerability scanner adapter.

Nuclei is opt-in (``SCANNER_ADVANCED_SECURITY_ENABLED``) because its templates
send real vulnerability probes.  Execution is delegated to the resource-bounded
sandbox; the orchestrator supplies the validated target and the remaining scan
budget through :class:`~scanners.base.ScanContext`.

``execute()`` is overridden so the template scan runs exactly once and yields
both the aggregated ``ScanResult`` and the granular findings.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
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
from scanners.executors.sandbox import (
    SandboxError,
    SandboxMode,
    get_sandbox_executor,
)
from scanners.features import advanced_security_enabled
from scanners.parsers.nuclei import parse_nuclei_jsonl
from scanners.security.target_validator import validate_target

logger = logging.getLogger(__name__)

_NUCLEI_SEVERITY_MAP = {
    "info": Severity.INFO,
    "low": Severity.LOW,
    "medium": Severity.MEDIUM,
    "high": Severity.HIGH,
    "critical": Severity.CRITICAL,
}


class NucleiScanner(BaseScanner):
    """Nuclei template scanner adapter (advanced security tier)."""

    name = "nuclei"
    scanner_type = ScannerType.CLI
    _binary = "nuclei"
    requires_advanced_security = True
    scanner_version = "1.1"

    @property
    def _cfg(self) -> dict[str, Any]:
        return getattr(settings, "SCANNER_CONFIG", {}).get("nuclei", {}) or {}

    @property
    def profile(self) -> dict[str, Any]:
        """Explicit execution profile (``standard`` or ``deep``).

        The profile owns every CLI parameter.  Request data never selects it:
        only the trusted deployment settings do, so a client cannot ask for a
        longer timeout or a more intrusive template set.
        """
        cfg = self._cfg
        name = str(cfg.get("profile") or "standard").strip().lower()
        profiles = cfg.get("profiles") or {}
        selected = profiles.get(name) or profiles.get("standard") or {}
        profile = dict(selected)
        profile.setdefault("name", name if selected else "legacy")
        # Backward compatibility with the pre-profile configuration keys.
        profile.setdefault("tags", cfg.get("tags", ["cve", "exposure", "misconfig"]))
        profile.setdefault("timeout", cfg.get("timeout", 170))
        profile.setdefault("request_timeout", cfg.get("request_timeout", 10))
        profile.setdefault("retries", cfg.get("retries", 1))
        profile.setdefault("concurrency", cfg.get("concurrency", 10))
        profile.setdefault("bulk_size", cfg.get("bulk_size", 25))
        profile.setdefault("rate_limit", cfg.get("rate_limit", 150))
        profile.setdefault("max_host_error", cfg.get("max_host_error", 30))
        profile.setdefault("severity", cfg.get("severity", ""))
        profile.setdefault("protocol", "")
        profile.setdefault("exclude_tags", [])
        profile.setdefault("ip_version", "4")
        return profile

    @property
    def profile_timeout(self) -> int:
        """Hard wall-clock budget owned by the active profile.

        The orchestrator must use this value, not the legacy top-level
        ``SCANNER_CONFIG["nuclei"]["timeout"]``: otherwise a profile with a
        shorter budget is silently given the old, larger sandbox timeout.
        """
        try:
            return max(1, int(self.profile.get("timeout", 150)))
        except (TypeError, ValueError):
            return 150

    @property
    def duration_alert_s(self) -> int:
        """Soft threshold above which a run is reported as late."""
        try:
            return max(1, int(self.profile.get("duration_alert_s", 150)))
        except (TypeError, ValueError):
            return 150

    @property
    def timeout(self) -> int:  # type: ignore[override]
        return self.profile_timeout

    @property
    def _templates_path(self) -> str:
        return str(self._cfg.get("templates_path", "") or "").strip()

    @property
    def binary_version(self) -> str:
        """Deployment-reported Nuclei version, or ``unknown``.

        The binary does not print its version during a normal scan, so the
        value must be supplied by the deployment (image tag / release).  We do
        not execute a second ``nuclei -version`` process just to label an
        archive: that would add a container start to every scan.
        """
        return str(self._cfg.get("binary_version", "") or "unknown").strip()

    @property
    def templates_version(self) -> str:
        """Deployment-reported template catalogue version, or ``unknown``."""
        return str(
            self._cfg.get("templates_version", "") or "unknown"
        ).strip()

    # ------------------------------------------------------------------
    # Availability / gate
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Available only when the advanced tier is enabled and the tool exists."""
        if not advanced_security_enabled():
            return False

        templates_path = self._templates_path
        if templates_path and not os.path.isdir(templates_path):
            # A configured but missing template repository would make Nuclei
            # exit immediately; report it as unavailable instead of creating
            # a misleading "0 vulnerabilities" result.
            return False

        executor = get_sandbox_executor()
        if executor.mode == SandboxMode.DOCKER:
            return executor.is_available(self.name)
        return shutil.which(self._binary) is not None

    def _disabled_outcome(self) -> ScanOutcome:
        message = (
            "Advanced security scanners are disabled "
            "(SCANNER_ADVANCED_SECURITY_ENABLED=false)"
        )
        return ScanOutcome(
            result=self._create_result(
                score=None,
                status="neutral",
                message=message,
                recommendation=(
                    "Enable SCANNER_ADVANCED_SECURITY_ENABLED only on a "
                    "dedicated, authorized scan worker."
                ),
            ),
            findings=[
                NormalizedFinding(
                    check_code="nuclei.disabled",
                    category="security",
                    severity=Severity.INFO,
                    status=FindingStatus.NOT_APPLICABLE,
                    title="Nuclei disabled by feature flag",
                    description=message,
                )
            ],
        )

    def _unavailable_outcome(self) -> ScanOutcome:
        return ScanOutcome(
            result=self._create_result(
                score=None,
                status="neutral",
                message="Nuclei not available — skipped",
                recommendation="Install nuclei to enable template-based scanning.",
            ),
            findings=[
                NormalizedFinding(
                    check_code="nuclei.unavailable",
                    category="security",
                    severity=Severity.INFO,
                    status=FindingStatus.NOT_APPLICABLE,
                    title="Nuclei not available",
                    recommendation="Install nuclei to enable template-based scanning.",
                )
            ],
        )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def scan(self, domain: str) -> ScanResult:
        return self.execute(domain).result

    def scan_findings(
        self,
        domain: str,
        result: ScanResult | None = None,
    ) -> list[NormalizedFinding]:
        """Legacy entry point; runs the tool once via :meth:`execute`."""
        return self.execute(domain).findings

    # ------------------------------------------------------------------
    # Completeness / partial results
    # ------------------------------------------------------------------

    @staticmethod
    def _stats_from_stderr(stderr: str) -> dict[str, Any] | None:
        """Return the last ``-stats -sj`` JSON object written by Nuclei.

        Nuclei streams a JSON stats object to stderr every ``-si`` seconds and
        a final one when the scan ends.  They are the only reliable way to
        distinguish a real 100% run from an early host skip (which still exits
        with code 0 and prints "Scan completed").
        """
        last: dict[str, Any] | None = None
        for line in (stderr or "").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except (TypeError, ValueError):
                continue
            if (
                isinstance(payload, dict)
                and "percent" in payload
                and "requests" in payload
            ):
                last = payload
        return last

    @staticmethod
    def _host_was_skipped(stderr: str) -> bool:
        """True when Nuclei dropped the target after repeated host errors.

        This is *not* a successful empty scan: Nuclei logs "Skipped <host> …
        unresponsive permanently" and still exits 0.  Treating it as complete
        would resolve every existing finding.
        """
        text = stderr or ""
        return (
            "unresponsive permanently" in text
            or ("Skipped " in text and "from target list" in text)
        )

    def _partial_finding(
        self,
        *,
        check_code: str,
        title: str,
        description: str,
    ) -> NormalizedFinding:
        return NormalizedFinding(
            check_code=check_code,
            category="security",
            severity=Severity.INFO,
            status=FindingStatus.UNKNOWN,
            title=title,
            description=description[:1000],
        )

    def execute(
        self,
        domain: str,
        context: ScanContext | None = None,
    ) -> ScanOutcome:
        if not advanced_security_enabled():
            return self._disabled_outcome()

        if not self.is_available():
            return self._unavailable_outcome()

        try:
            target = (
                context.target
                if context is not None and context.target is not None
                else validate_target(f"https://{domain}")
            )
        except TargetValidationError as exc:
            return ScanOutcome(
                result=self._create_result(
                    score=None,
                    status="critical",
                    message=str(exc),
                ),
                findings=[
                    NormalizedFinding(
                        check_code="nuclei.target_validation",
                        category="security",
                        severity=Severity.HIGH,
                        status=FindingStatus.FAIL,
                        title="Target validation failed",
                        description=str(exc),
                    )
                ],
            )

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

        templates_path = self._templates_path
        docker_templates = "/nuclei-templates"
        container_templates = (
            docker_templates
            if templates_path and executor.mode == SandboxMode.DOCKER
            else templates_path
        )

        try:
            command_result = executor.run(
                command=self.build_command(
                    target.url,
                    templates_path=container_templates or None,
                ),
                limits=limits,
                scanner_name=self.name,
                # Official Nuclei images set the binary as ENTRYPOINT.  Clear
                # it so the command above is not passed as "nuclei nuclei …".
                docker_entrypoint="",
                mounts=[(templates_path, docker_templates)]
                if templates_path and executor.mode == SandboxMode.DOCKER
                else None,
                env_extra={"NUCLEI_TEMPLATES_PATH": container_templates}
                if container_templates
                else None,
            )
        except SandboxError as exc:
            logger.error("Nuclei sandbox unavailable: %s", exc)
            return ScanOutcome(
                result=self._create_result(
                    score=None,
                    status="warning",
                    message=f"Nuclei could not be started safely: {exc}",
                ),
                findings=[
                    NormalizedFinding(
                        check_code="nuclei.sandbox_unavailable",
                        category="security",
                        severity=Severity.MEDIUM,
                        status=FindingStatus.UNKNOWN,
                        title="Nuclei sandbox unavailable",
                        description=str(exc),
                    )
                ],
            )

        parsed = parse_nuclei_jsonl(command_result.stdout)
        findings = self.normalize(parsed)
        high = [
            item for item in parsed
            if item.get("severity") in ("high", "critical")
        ]
        medium = [
            item for item in parsed
            if item.get("severity") == "medium"
        ]
        stats = self._stats_from_stderr(command_result.stderr)
        host_skipped = self._host_was_skipped(command_result.stderr)

        percent: int | None = None
        if stats is not None:
            try:
                percent = int(float(stats.get("percent") or 0))
            except (TypeError, ValueError):
                percent = None

        # A scan is complete only when the process ended cleanly, the target
        # was not dropped, Nuclei itself reported 100% progress, and its JSONL
        # was not truncated by the subprocess output cap.  A truncated report
        # is missing findings that were actually emitted, so resolving on it
        # would be unsafe.  An empty but complete report is still
        # authoritative: it can resolve older findings.
        complete = bool(
            command_result.exit_code == 0
            and not command_result.timed_out
            and not command_result.memory_exceeded
            and not host_skipped
            and not command_result.output_truncated
            and percent is not None
            and percent >= 100
        )

        meta: NormalizedFinding | None = None
        partial_reason = ""
        if command_result.timed_out:
            partial_reason = "timeout"
            meta = self._partial_finding(
                check_code="nuclei.timeout",
                title="Nuclei stopped by the sandbox (timeout)",
                description=command_result.stderr,
            )
        elif command_result.memory_exceeded:
            partial_reason = "memory_limit"
            meta = self._partial_finding(
                check_code="nuclei.memory_exceeded",
                title="Nuclei stopped by the sandbox (memory limit)",
                description=command_result.stderr,
            )
        elif host_skipped:
            partial_reason = "host_unresponsive"
            meta = self._partial_finding(
                check_code="nuclei.host_unresponsive",
                title="Nuclei target became unreachable",
                description=command_result.stderr,
            )
        elif command_result.exit_code != 0:
            partial_reason = "exit_code"
            meta = self._partial_finding(
                check_code="nuclei.execution_failed",
                title="Nuclei exited with an error",
                description=command_result.stderr,
            )
        elif command_result.output_truncated:
            # The process succeeded, but the subprocess cap cut the JSONL.
            # Some real findings are absent from the captured report, so it
            # cannot prove that older findings are gone.
            partial_reason = "output_truncated"
            meta = self._partial_finding(
                check_code="nuclei.output_truncated",
                title="Nuclei output was truncated",
                description=(
                    "The scanner output exceeded the configured capture "
                    "limit; the report is incomplete."
                ),
            )
        elif percent is None:
            partial_reason = "missing_stats"
            meta = self._partial_finding(
                check_code="nuclei.incomplete",
                title="Nuclei did not report scan completion",
                description=command_result.stderr,
            )
        elif percent < 100:
            partial_reason = "incomplete"
            meta = self._partial_finding(
                check_code="nuclei.incomplete",
                title="Nuclei scan did not complete",
                description=command_result.stderr,
            )

        if partial_reason or not complete:
            status = "warning"
        elif high:
            status = "critical"
        elif medium:
            status = "warning"
        else:
            status = "neutral"

        duration_over_alert = (
            command_result.duration_ms > self.duration_alert_s * 1000
        )
        if duration_over_alert:
            logger.warning(
                "Nuclei profile '%s' exceeded its %ds alert threshold "
                "(duration=%dms, complete=%s) for scan %s",
                self.profile.get("name", "standard"),
                self.duration_alert_s,
                command_result.duration_ms,
                complete,
                getattr(context, "scan_id", None),
            )

        message = (
            f"Nuclei incomplete ({partial_reason}); "
            f"{len(parsed)} finding(s) from partial output"
            if partial_reason
            else (
                f"Nuclei found {len(parsed)} template match(es), "
                f"{len(high)} high/critical"
            )
        )

        return ScanOutcome(
            result=self._create_result(
                score=None,
                status=status,
                message=message,
                duration_ms=command_result.duration_ms,
                findings_count=len(parsed),
                high_severity_count=len(high),
                exit_code=command_result.exit_code,
                timed_out=command_result.timed_out,
                memory_exceeded=command_result.memory_exceeded,
                output_truncated=command_result.output_truncated,
                scan_complete=complete,
                partial_reason=partial_reason,
                profile=self.profile.get("name", "standard"),
                profile_timeout_s=self.profile_timeout,
                duration_alert_s=self.duration_alert_s,
                duration_over_alert=duration_over_alert,
                # Conservative default: a profile narrower than the catalog
                # can add/update findings but cannot prove an old one is gone.
                resolve_missing=bool(self.profile.get("resolve_missing", True)),
                host_skipped=host_skipped,
                percent=percent,
                templates_loaded=(stats or {}).get("templates"),
                requests=(stats or {}).get("requests"),
                errors=(stats or {}).get("errors"),
                stats=stats or {},
            ),
            findings=([meta] if meta is not None else []) + findings,
            raw_report=command_result.stdout,
            raw_report_format="nuclei-jsonl",
            raw_report_meta={
                "scanner_version": self.binary_version,
                "adapter_version": self.scanner_version,
                "templates_version": self.templates_version,
                "templates_path": templates_path,
                "profile": self.profile.get("name", "standard"),
                "profile_timeout_s": self.profile_timeout,
                "duration_ms": command_result.duration_ms,
                "exit_code": command_result.exit_code,
                "timed_out": command_result.timed_out,
                "memory_exceeded": command_result.memory_exceeded,
                "output_truncated": command_result.output_truncated,
                "scan_complete": complete,
                "partial_reason": partial_reason,
                "host_skipped": host_skipped,
                "percent": percent,
                "templates_loaded": (stats or {}).get("templates"),
                "requests": (stats or {}).get("requests"),
                "errors": (stats or {}).get("errors"),
                "target": target.url,
                "stderr_excerpt": command_result.stderr[-4000:],
            },
        )

    # ------------------------------------------------------------------
    # Command / parsing / normalization
    # ------------------------------------------------------------------

    def build_command(
        self,
        target: str,
        options: dict | None = None,
        templates_path: str | None = None,
    ) -> list[str]:
        profile = self.profile
        tags = profile.get("tags") or []
        tags_value = ",".join(tags) if isinstance(tags, list) else str(tags)
        exclude_value = ",".join(profile.get("exclude_tags") or [])

        command = [
            self._binary,
            "-u",
            target,
            "-jsonl",
            "-no-color",
            "-disable-update-check",
            # JSON stats every 5 s: the final record proves the run reached
            # 100% and lets the adapter detect an early host skip.
            "-stats",
            "-stats-json",
            "-stats-interval",
            "5",
            "-timeout",
            str(int(profile.get("request_timeout", 5))),
            "-retries",
            str(int(profile.get("retries", 1))),
            "-bulk-size",
            str(int(profile.get("bulk_size", 10))),
            "-concurrency",
            str(int(profile.get("concurrency", 20))),
            "-rate-limit",
            str(int(profile.get("rate_limit", 60))),
            "-max-host-error",
            str(int(profile.get("max_host_error", 40))),
            "-ip-version",
            str(profile.get("ip_version") or "4"),
        ]
        protocol = str(profile.get("protocol") or "").strip()
        if protocol:
            command += ["-type", protocol]
        if tags_value:
            command += ["-tags", tags_value]
        if exclude_value:
            command += ["-exclude-tags", exclude_value]
        if templates_path:
            command += ["-t", templates_path]

        severity = str(profile.get("severity", "") or "").strip()
        if severity:
            command += ["-severity", severity]

        return command

    def parse(self, output: str) -> list[dict[str, Any]]:
        return parse_nuclei_jsonl(output)

    def normalize(self, parsed_results: list[dict[str, Any]]) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        seen: set[tuple[str, str]] = set()

        for item in parsed_results:
            sev_raw = str(item.get("severity", "info")).lower()
            severity = _NUCLEI_SEVERITY_MAP.get(sev_raw, Severity.MEDIUM)
            status = (
                FindingStatus.FAIL
                if sev_raw in ("high", "critical")
                else FindingStatus.WARNING
            )

            template_id = str(item.get("template_id", "unknown") or "unknown")
            matched_at = str(item.get("matched_at", "") or "")
            key = (template_id, matched_at)
            if key in seen:
                continue
            seen.add(key)

            refs = item.get("reference", [])
            ref_url = refs[0] if isinstance(refs, list) and refs else ""

            findings.append(
                NormalizedFinding(
                    check_code=f"nuclei.{template_id}"[:128],
                    category="security",
                    severity=severity,
                    status=status,
                    title=str(item.get("name") or "Nuclei template match")[:255],
                    description=str(item.get("description") or ""),
                    evidence={
                        "template_id": template_id,
                        "matched_at": matched_at,
                        "matcher_name": item.get("matcher_name", ""),
                        "extracted_results": item.get("extracted_results", []),
                        "tags": item.get("tags", []),
                        "host": item.get("host", ""),
                        "ip": item.get("ip", ""),
                    },
                    recommendation=(
                        "Review the template documentation and apply the "
                        "suggested fix."
                    ),
                    reference_url=ref_url if isinstance(ref_url, str) else "",
                )
            )

        return findings


nuclei_scanner = NucleiScanner()
