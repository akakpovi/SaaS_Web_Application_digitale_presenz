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
import re
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
    def profile_name(self) -> str:
        """Configured default profile, selected only by deployment settings."""
        return str(self._cfg.get("profile") or "standard").strip().lower()

    def profile_for(self, name: str | None = None) -> dict[str, Any]:
        """Return an explicit execution profile.

        ``name`` comes from a trusted step definition (the stage-2 journey
        profile) or from deployment settings.  Request data never selects it,
        so a client cannot ask for a longer timeout or a more intrusive set.
        """
        cfg = self._cfg
        selected_name = str(name or self.profile_name or "standard").strip().lower()
        profiles = cfg.get("profiles") or {}
        selected = profiles.get(selected_name) or profiles.get("standard") or {}
        profile = dict(selected)
        profile.setdefault("name", selected_name if selected else "legacy")
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
        profile.setdefault("extra_args", [])
        profile.setdefault("template_paths", [])
        return profile

    @property
    def profile(self) -> dict[str, Any]:
        return self.profile_for()

    def timeout_for_profile(self, name: str | None = None) -> int:
        """Hard wall-clock budget owned by *name* (defaults to the profile)."""
        try:
            return max(1, int(self.profile_for(name).get("timeout", 150)))
        except (TypeError, ValueError):
            return 150

    def duration_alert_for_profile(self, name: str | None = None) -> int:
        """Soft threshold above which a run of *name* is reported as late."""
        profile = self.profile_for(name)
        try:
            return max(1, int(profile.get("duration_alert_s", 150)))
        except (TypeError, ValueError):
            return 150

    @property
    def profile_timeout(self) -> int:
        """Hard wall-clock budget owned by the active profile.

        The orchestrator must use this value, not the legacy top-level
        ``SCANNER_CONFIG["nuclei"]["timeout"]``: otherwise a profile with a
        shorter budget is silently given the old, larger sandbox timeout.
        """
        return self.timeout_for_profile()

    @property
    def duration_alert_s(self) -> int:
        """Soft threshold above which a run is reported as late."""
        return self.duration_alert_for_profile()

    @property
    def timeout(self) -> int:  # type: ignore[override]
        return self.profile_timeout

    @property
    def _templates_path(self) -> str:
        return str(self._cfg.get("templates_path", "") or "").strip()

    @property
    def _scenario_templates_path(self) -> str:
        """Host directory holding the stage-2 ``selected/`` and ``presence/``."""
        return str(self._cfg.get("scenario_templates_path", "") or "").strip()

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
        return str(self._cfg.get("templates_version", "") or "unknown").strip()

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
                # A skipped run proves nothing about the target.  Without
                # this flag the orchestrator's legacy fallback would treat
                # the run as complete and could resolve older findings.
                scan_complete=False,
                partial_reason="unavailable",
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
        return "unresponsive permanently" in text or (
            "Skipped " in text and "from target list" in text
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

        profile_name = (
            context.profile
            if context is not None and getattr(context, "profile", None)
            else self.profile_name
        )
        profile = self.profile_for(profile_name)
        profile_timeout = self.timeout_for_profile(profile_name)
        profile_label = str(profile.get("name", "standard"))
        duration_alert_s = self.duration_alert_for_profile(profile_name)
        resolve_missing = bool(profile.get("resolve_missing", True))

        timeout = (
            context.effective_timeout(profile_timeout)
            if context is not None
            else profile_timeout
        )
        executor = get_sandbox_executor()
        limits = (
            context.sandbox_limits
            if context is not None and context.sandbox_limits is not None
            else executor.limits_for(self.name, timeout=timeout)
        )

        templates_root = self._templates_path
        scenario_templates_root = self._scenario_templates_path
        profile_paths = [
            str(path).strip()
            for path in (profile.get("template_paths") or [])
            if str(path).strip()
        ]
        docker_templates = "/nuclei-templates"
        mounts: list[tuple[str, str]] | None = None
        env_templates = ""

        if profile_paths:
            container_scenario_root = "/opt/scanner-templates"
            if executor.mode == SandboxMode.DOCKER:
                # The assets may be baked into a dedicated image at these
                # container paths.  When the host directory is configured it
                # is mounted over the same root, so the stock Nuclei image can
                # use the repository selection without a custom build.
                template_paths_used = profile_paths
                env_templates = container_scenario_root
                if scenario_templates_root:
                    mounts = [(scenario_templates_root, container_scenario_root)]
            else:
                # Process mode has no container: resolve the profile's
                # subdirectories under the scenario root, then under the full
                # catalogue root for deployments that co-locate them.
                host_root = scenario_templates_root or templates_root
                if not host_root:
                    # Process mode runs from the application tree: the assets
                    # shipped with the repository are a valid fallback.
                    host_root = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "templates",
                    )
                template_paths_used = (
                    [
                        os.path.join(host_root, os.path.basename(path.rstrip("/")))
                        for path in profile_paths
                    ]
                    if host_root
                    else profile_paths
                )
        else:
            container_templates = (
                docker_templates
                if templates_root and executor.mode == SandboxMode.DOCKER
                else templates_root
            )
            template_paths_used = [container_templates] if container_templates else []
            env_templates = container_templates
            if templates_root and executor.mode == SandboxMode.DOCKER:
                mounts = [(templates_root, docker_templates)]

        try:
            command_result = executor.run(
                command=self.build_command(
                    target.url,
                    templates_path=(
                        template_paths_used[0] if template_paths_used else None
                    ),
                    template_paths=template_paths_used or None,
                    profile_name=profile_name,
                ),
                limits=limits,
                scanner_name=self.name,
                # Official Nuclei images set the binary as ENTRYPOINT.  Clear
                # it so the command above is not passed as "nuclei nuclei …".
                docker_entrypoint="",
                mounts=mounts,
                env_extra={"NUCLEI_TEMPLATES_PATH": env_templates}
                if env_templates
                else None,
            )
        except SandboxError as exc:
            logger.error("Nuclei sandbox unavailable: %s", exc)
            return ScanOutcome(
                result=self._create_result(
                    score=None,
                    status="warning",
                    message=f"Nuclei could not be started safely: {exc}",
                    # The tool never ran: this is the exact case that used to
                    # become a false "completed" journey.  The orchestrator
                    # maps an explicit ``scan_complete=False`` to PARTIAL.
                    scan_complete=False,
                    partial_reason="sandbox_unavailable",
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
        # Stage 2 needs one finding per missing header.  Nuclei emits one JSONL
        # record per matcher for ``http-missing-security-headers`` (ten on a
        # typical target), all sharing the same template id and matched URL.
        # Classic profiles keep their historical single-finding aggregation.
        findings = self.normalize(
            parsed, preserve_matchers=(profile_name == "scenario_c")
        )
        critical = [item for item in parsed if item.get("severity") == "critical"]
        high = [item for item in parsed if item.get("severity") == "high"]
        high_or_critical = [
            item for item in parsed if item.get("severity") in ("high", "critical")
        ]
        medium = [item for item in parsed if item.get("severity") == "medium"]
        low = [item for item in parsed if item.get("severity") == "low"]
        # Nuclei is a 20-point scorecard. Critical/high findings dominate the
        # penalty; medium and low findings are still visible without making
        # the score meaningless on a noisy template catalog.
        nuclei_score = max(
            0,
            20 - 10 * len(critical) - 5 * len(high) - 2 * len(medium) - len(low),
        )
        stats = self._stats_from_stderr(command_result.stderr)
        host_skipped = self._host_was_skipped(command_result.stderr)

        percent: int | None = None
        if stats is not None:
            try:
                percent = int(float(stats.get("percent") or 0))
            except (TypeError, ValueError):
                percent = None

        raw_templates = (stats or {}).get("templates")
        try:
            templates_loaded = None if raw_templates is None else int(raw_templates)
        except (TypeError, ValueError):
            templates_loaded = None

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
            # A scan that loaded zero templates proves nothing: the profile
            # assets are missing from the image or the mounted path.
            and (templates_loaded is None or templates_loaded > 0)
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
        elif templates_loaded == 0:
            partial_reason = "no_templates"
            meta = self._partial_finding(
                check_code="nuclei.no_templates",
                title="Nuclei loaded no templates",
                description=(
                    "Nuclei reported 0 loaded templates; the profile assets "
                    "are missing from the image or the mounted path."
                ),
            )

        if partial_reason or not complete:
            status = "warning"
        elif high_or_critical:
            status = "critical"
        elif medium:
            status = "warning"
        else:
            status = "neutral"

        duration_over_alert = command_result.duration_ms > duration_alert_s * 1000
        if duration_over_alert:
            logger.warning(
                "Nuclei profile '%s' exceeded its %ds alert threshold "
                "(duration=%dms, complete=%s) for scan %s",
                profile_label,
                duration_alert_s,
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
                f"{len(high_or_critical)} high/critical"
            )
        )

        return ScanOutcome(
            result=self._create_result(
                score=nuclei_score,
                status=status,
                message=message,
                duration_ms=command_result.duration_ms,
                findings_count=len(parsed),
                critical_count=len(critical),
                high_severity_count=len(high_or_critical),
                exit_code=command_result.exit_code,
                timed_out=command_result.timed_out,
                memory_exceeded=command_result.memory_exceeded,
                output_truncated=command_result.output_truncated,
                scan_complete=complete,
                partial_reason=partial_reason,
                profile=profile_label,
                profile_timeout_s=profile_timeout,
                duration_alert_s=duration_alert_s,
                duration_over_alert=duration_over_alert,
                # Conservative default: a profile narrower than the catalog
                # can add/update findings but cannot prove an old one is gone.
                resolve_missing=resolve_missing,
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
                "templates_path": template_paths_used,
                "profile": profile_label,
                "profile_timeout_s": profile_timeout,
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
        *,
        template_paths: list[str] | None = None,
        profile_name: str | None = None,
    ) -> list[str]:
        profile = self.profile_for(profile_name)
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

        selected_paths = [
            str(path)
            for path in (template_paths or profile.get("template_paths") or [])
            if str(path).strip()
        ]
        if selected_paths:
            for path in selected_paths:
                command += ["-t", path]
        elif templates_path:
            command += ["-t", templates_path]

        severity = str(profile.get("severity", "") or "").strip()
        if severity:
            command += ["-severity", severity]

        extra_args = profile.get("extra_args") or []
        if isinstance(extra_args, str):
            extra_args = extra_args.split()
        command += [str(arg) for arg in extra_args if str(arg).strip()]

        return command

    def parse(self, output: str) -> list[dict[str, Any]]:
        return parse_nuclei_jsonl(output)

    def normalize(
        self,
        parsed_results: list[dict[str, Any]],
        *,
        preserve_matchers: bool = False,
    ) -> list[NormalizedFinding]:
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
            matcher_name = str(item.get("matcher_name", "") or "").strip()
            check_code = f"nuclei.{template_id}"[:128]
            key = (template_id, matched_at)
            if (
                preserve_matchers
                and template_id == "http-missing-security-headers"
                and matcher_name
            ):
                # One missing header = one actionable finding.  The matcher
                # name is the header identifier (e.g. ``content-security-policy``).
                matcher_slug = re.sub(r"[^a-z0-9]+", "-", matcher_name.lower()).strip(
                    "-"
                )
                if matcher_slug:
                    check_code = f"nuclei.{template_id}.{matcher_slug}"[:128]
                    key = (check_code, matched_at)
            if key in seen:
                continue
            seen.add(key)

            refs = item.get("reference", [])
            ref_url = refs[0] if isinstance(refs, list) and refs else ""

            findings.append(
                NormalizedFinding(
                    check_code=check_code,
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
                        "Review the template documentation and apply the suggested fix."
                    ),
                    reference_url=ref_url if isinstance(ref_url, str) else "",
                )
            )

        return findings


nuclei_scanner = NucleiScanner()
