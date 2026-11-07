"""testssl.sh TLS/SSL scanner adapter."""

from __future__ import annotations

import logging
import os
import shutil
from collections import Counter
from dataclasses import replace
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
from scanners.implementations.tool_run import (
    ToolRun,
    build_outcome,
    evaluate_completeness,
    read_report_file,
    report_workdir,
    target_validation_outcome,
    unavailable_outcome,
)
from scanners.parsers.testssl import parse_testssl_json
from scanners.security.target_validator import validate_target

logger = logging.getLogger(__name__)

#: Deductions applied to the 20-point SSL category.  A testssl finding is
#: counted once after normalisation (the parser may repeat a check per IP).
_SSL_SEVERITY_PENALTY = {
    "critical": 10,
    "high": 5,
    "medium": 2,
    "low": 1,
}


class TestSSLScanner(BaseScanner):
    """testssl.sh TLS/SSL configuration scanner adapter."""

    name = "testssl"
    scanner_type = ScannerType.CLI
    _binary = "testssl"

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("testssl", {}).get("timeout", 60)

    def is_available(self) -> bool:
        executor = get_sandbox_executor()
        if executor.mode == SandboxMode.DOCKER:
            return executor.is_available(self.name)
        return (
            shutil.which("testssl") is not None
            or shutil.which("testssl.sh") is not None
        )

    def _get_binary(self) -> str:
        """Return the binary name to invoke.

        Inside the sandbox the name comes from settings: the image ships the
        Debian package, which installs ``/usr/bin/testssl``.  On a host where
        the tool is present under either name (process mode), probe for it.
        """
        executor = get_sandbox_executor()
        if executor.mode == SandboxMode.DOCKER:
            cfg = getattr(settings, "SCANNER_CONFIG", {}).get(self.name, {})
            return str(cfg.get("binary") or "testssl")
        return "testssl" if shutil.which("testssl") else "testssl.sh"

    def _ok_exit_codes(self) -> tuple[int, ...]:
        """Exit codes that mean "the TLS scan ran to the end".

        testssl.sh exits 0 after a completed run whatever the severities it
        reported (``exit $ALLOK`` with ``declare -r ALLOK=0``); 244–255 are its
        fatal/abort codes (resources, connectivity, DNS, child signal, …).  A
        non-zero code therefore means the report cannot be trusted as a full
        coverage statement.
        """
        cfg = getattr(settings, "SCANNER_CONFIG", {}).get(self.name, {})
        raw = cfg.get("ok_exit_codes")
        if isinstance(raw, (list, tuple)) and raw:
            try:
                return tuple(int(code) for code in raw)
            except (TypeError, ValueError):
                pass
        return (0,)

    def scan(self, domain: str) -> ScanResult:
        return self.execute(domain).result

    def execute(
        self,
        domain: str,
        context: ScanContext | None = None,
    ) -> ScanOutcome:
        """Run testssl.sh once and return the result + normalized findings.

        The tool used to be executed twice per scan (once by ``scan()`` and
        once by ``scan_findings()``).  Delegation now goes through the
        sandboxed executor and both artefacts are derived from one run.
        """
        if not self.is_available():
            return build_outcome(
                self,
                run=ToolRun(exit_code=-1),
                findings=[NormalizedFinding(
                    check_code="testssl.unavailable",
                    category="ssl",
                    severity=Severity.INFO,
                    status=FindingStatus.NOT_APPLICABLE,
                    title="testssl.sh not available",
                    recommendation="Install testssl.sh for comprehensive TLS analysis.",
                )],
                message="testssl.sh not available — skipped",
                status="neutral",
                recommendation="Install testssl.sh for deep TLS analysis.",
                scan_complete=False,
                partial_reason="unavailable",
            )

        try:
            target_info = (
                context.target
                if context is not None and context.target is not None
                else validate_target(f"https://{domain}")
            )
        except TargetValidationError as exc:
            return target_validation_outcome(
                self, error=str(exc), category="ssl"
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
        # testssl.sh writes its human-readable table and the JSON report to
        # different streams; --jsonfile /dev/stdout would interleave them.  The
        # report is therefore written to a file inside a directory the sandbox
        # binds from the host, which also gives the archiver a real artefact.
        try:
            if executor.mode == SandboxMode.DOCKER:
                with report_workdir("presence-testssl-") as workdir:
                    return self._run_into_workdir(
                        target_info=target_info,
                        workdir=workdir,
                        executor=executor,
                        limits=limits,
                    )

            run = ToolRun.from_command_result(
                executor.run(
                    command=self.build_command(target_info.hostname),
                    limits=limits,
                    scanner_name=self.name,
                ),
                max_output_bytes=executor.max_output_bytes,
            )
        except SandboxError as exc:
            logger.error("testssl.sh sandbox unavailable: %s", exc)
            return unavailable_outcome(self, reason=str(exc))

        return self._outcome_from_run(
            run,
            report=run.stdout,
            report_truncated=False,
            timeout_s=limits.timeout_s,
        )

    def _run_into_workdir(
        self,
        *,
        target_info: Any,
        workdir: str,
        executor: Any,
        limits: Any,
    ) -> ScanOutcome:
        """Docker mode: mount a host directory and read the JSON from there."""
        container_dir = "/tmp/testssl-report"
        report_path = f"{container_dir}/testssl.json"
        run = ToolRun.from_command_result(
            executor.run(
                command=self.build_command(
                    target_info.hostname, jsonfile=report_path
                ),
                limits=limits,
                scanner_name=self.name,
                mounts=[(workdir, container_dir)],
            ),
            max_output_bytes=executor.max_output_bytes,
        )
        report, truncated = read_report_file(
            os.path.join(workdir, "testssl.json")
        )
        return self._outcome_from_run(
            run,
            report=report,
            report_truncated=truncated,
            timeout_s=limits.timeout_s,
        )

    def _outcome_from_run(
        self,
        run: ToolRun,
        *,
        report: str,
        report_truncated: bool,
        timeout_s: int,
    ) -> ScanOutcome:
        """Build the outcome from one run plus its collected JSON report."""
        if report_truncated:
            run = replace(run, output_truncated=True)

        if run.timed_out:
            finding = NormalizedFinding(
                check_code="testssl.timeout",
                category="ssl",
                severity=Severity.INFO,
                status=FindingStatus.UNKNOWN,
                title=f"testssl.sh timed out after {timeout_s}s",
                duration_ms=run.duration_ms,
            )
            return build_outcome(
                self,
                run=run,
                findings=[finding],
                message=f"testssl.sh timed out after {timeout_s}s",
                status="warning",
                scan_complete=False,
                partial_reason="timeout",
            )

        complete, reason = evaluate_completeness(
            run, ok_exit_codes=self._ok_exit_codes(), requires_output=False
        )
        if complete and not report.strip():
            # No JSON report at all: the run proves nothing about TLS state.
            complete, reason = False, "empty_report"
        elif complete and not self._looks_like_testssl_json(report):
            complete, reason = False, "unparsable_report"
        parsed = parse_testssl_json(report)
        high_sev = [p for p in parsed if p.get("severity") in ("high", "critical")]
        findings = self.normalize(parsed)
        severity_counts = Counter(finding.severity for finding in findings)
        penalty = sum(
            _SSL_SEVERITY_PENALTY.get(severity, 0) * count
            for severity, count in severity_counts.items()
        )
        ssl_score = max(0, 20 - penalty)
        return build_outcome(
            self,
            run=run,
            findings=findings,
            message=(
                f"testssl.sh found {len(parsed)} check(s), "
                f"{len(high_sev)} high/critical"
                if complete
                else f"testssl.sh scan incomplete ({reason})"
            ),
            status=(
                ("critical" if high_sev else "neutral")
                if complete
                else "warning"
            ),
            score=ssl_score,
            scan_complete=complete,
            partial_reason=reason,
            total_checks=len(parsed),
            high_severity_count=len(high_sev),
            severity_counts=dict(severity_counts),
            ssl_score=ssl_score,
            raw_report=report or None,
            raw_report_format="testssl-json",
            raw_report_meta={"checks": len(parsed)},
        )

    @staticmethod
    def _looks_like_testssl_json(report: str) -> bool:
        """testssl.sh --jsonfile-pretty writes one JSON object."""
        text = (report or "").lstrip()
        return text.startswith("{") and text.rstrip().endswith("}")

    def scan_findings(
        self,
        domain: str,
        result: ScanResult | None = None,
    ) -> list[NormalizedFinding]:
        """Legacy entry point; runs the tool once via :meth:`execute`."""
        return self.execute(domain).findings

    def build_command(
        self,
        target: str,
        options: dict | None = None,
        *,
        jsonfile: str = "/dev/stdout",
    ) -> list[str]:
        # ``--std`` only tests cipher categories (upstream help: "tests
        # standard cipher categories by strength").  It does NOT test
        # protocols, certificate/server defaults, HSTS/security headers or
        # vulnerability probes.  The previous comment claimed the opposite and
        # the real report contained 0 protocols, 0 serverDefaults and 0
        # vulnerabilities.  Each missing category is therefore requested
        # explicitly below.
        #
        # ``--ip one`` limits the run to the first DNS address.  On the
        # multi-address Cloudflare target, scanning every address with the full
        # category set took 140 s (it would be killed at the 120 s step
        # timeout), while one address takes 65 s at rest and 100 s under four
        # CPU burners.  The
        # per-address divergence is therefore not covered by this step; the
        # step timeout and the 540 s whole-scan budget are unchanged.
        return [
            self._get_binary(),
            "--std",
            "--protocols",
            "--server-defaults",
            "--headers",
            "--vulnerable",
            "--ip", "one",
            "--jsonfile-pretty", jsonfile,
            "--quiet",
            "--nodns", "min",
            "--color", "0",
            "--parallel",
            "--", f"{target}:443",
        ]

    def parse(self, output: str) -> list[dict[str, Any]]:
        return parse_testssl_json(output)

    def normalize(self, parsed_results: list[dict[str, Any]]) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        severity_map = {
            "info": (Severity.INFO, FindingStatus.PASS),
            "low": (Severity.LOW, FindingStatus.WARNING),
            "medium": (Severity.MEDIUM, FindingStatus.WARNING),
            "high": (Severity.HIGH, FindingStatus.FAIL),
            "critical": (Severity.CRITICAL, FindingStatus.FAIL),
        }

        # The same check is evaluated against every resolved address: collapse
        # identical outcomes so the scan does not report the same TLS result
        # twice, while keeping the list of addresses it applies to.
        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for item in parsed_results:
            check_id = str(item.get("id") or "").strip()
            if not check_id:
                continue
            sev_raw = str(item.get("severity", "info")).lower()
            key = (check_id, sev_raw, str(item.get("finding", "")))
            entry = grouped.get(key)
            if entry is None:
                grouped[key] = {"item": item, "ips": [item.get("ip")]}
            else:
                ip = item.get("ip")
                if ip and ip not in entry["ips"]:
                    entry["ips"].append(ip)

        for (check_id, sev_raw, _finding_text), entry in grouped.items():
            item = entry["item"]
            severity, status = severity_map.get(sev_raw, (Severity.INFO, FindingStatus.PASS))

            cve = item.get("cve", "")
            ref = f"https://cve.mitre.org/cgi-bin/cvename.cgi?name={cve}" if cve else ""

            findings.append(NormalizedFinding(
                check_code=f"testssl.{check_id}",
                category="ssl",
                severity=severity,
                status=status,
                title=f"TLS check: {check_id}",
                description=item.get("finding", ""),
                evidence={**item, "addresses": entry["ips"]},
                reference_url=ref,
            ))

        return findings


testssl_scanner = TestSSLScanner()
