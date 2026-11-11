"""OWASP ZAP adapter (advanced security tier).

Two transports are supported:

``docker``
    The official ZAP image (``ghcr.io/zaproxy/zap-stable``) runs inside the
    resource-bounded sandbox on the dedicated, egress-filtered scanner
    network.  The baseline script performs passive scanning; its JSON report
    is written to a temporary directory bind-mounted at ``/zap/wrk`` and
    parsed after the container exits.  The ZAP baseline script only accepts file
    options below ``/zap/wrk`` and its automation framework duplicates that
    prefix, so the report directory is mounted there and the scan runs with
    ``--autooff``.

``api``
    A ZAP sidecar exposes its REST API.  Used when Docker sandbox mode is not
    configured.  Active scanning is opt-in (``SCANNER_ZAP_ACTIVE_SCAN``)
    because it sends intrusive payloads.

ZAP is opt-in through ``SCANNER_ADVANCED_SECURITY_ENABLED``: every entry point
refuses to run when the flag is off, independently of the orchestrator gate.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import time
from typing import Any

import requests as http_requests
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
    shared_work_dir,
)
from scanners.features import advanced_security_enabled
from scanners.parsers.zap import parse_zap_json
from scanners.security.target_validator import validate_target

logger = logging.getLogger(__name__)

_ZAP_SEVERITY_MAP = {
    "informational": Severity.INFO,
    "info": Severity.INFO,
    "low": Severity.LOW,
    "medium": Severity.MEDIUM,
    "high": Severity.HIGH,
    "critical": Severity.CRITICAL,
}

_FIRST_URL = re.compile(r"https?://[^\s,;]+")


def _first_reference_url(reference: str) -> str:
    match = _FIRST_URL.search(reference or "")
    return match.group(0)[:500] if match else ""


class ZAPScanner(BaseScanner):
    """OWASP ZAP scanner adapter (sandboxed Docker or REST sidecar)."""

    name = "zap"
    scanner_type = ScannerType.API
    scanner_version = "1.1"
    requires_advanced_security = True
    _binary = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @property
    def _cfg(self) -> dict[str, Any]:
        return getattr(settings, "SCANNER_CONFIG", {}).get("zap", {}) or {}

    @property
    def timeout(self) -> int:  # type: ignore[override]
        return int(self._cfg.get("timeout", 300))

    @property
    def _api_url(self) -> str:
        return str(self._cfg.get("api_url", "http://zap-scanner:8090")).rstrip("/")

    @property
    def _api_key(self) -> str:
        return str(self._cfg.get("api_key", "") or "")

    @property
    def _docker_image(self) -> str:
        configured = str(self._cfg.get("docker_image", "") or "").strip()
        if configured:
            return configured
        # Also honour SCANNER_SANDBOX["docker"]["images"]["zap"] so operators
        # only need one setting in Docker mode.
        return get_sandbox_executor().docker_image_for(self.name)

    @property
    def _transport(self) -> str:
        """Return ``docker`` or ``api`` according to configuration."""
        mode = str(self._cfg.get("mode", "auto")).strip().lower()
        if mode in ("docker", "api"):
            return mode

        executor = get_sandbox_executor()
        if executor.mode == SandboxMode.DOCKER and self._docker_image:
            return "docker"
        return "api"

    # ------------------------------------------------------------------
    # Availability / gate
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        if not advanced_security_enabled():
            return False

        if self._transport == "docker":
            executor = get_sandbox_executor()
            return (
                executor.mode == SandboxMode.DOCKER
                and executor.docker_available()
                and bool(self._docker_image)
            )
        return self._api_available()

    def _api_available(self) -> bool:
        try:
            response = http_requests.get(
                f"{self._api_url}/JSON/core/view/version/",
                headers=self._api_headers(),
                timeout=3,
            )
            return response.status_code == 200
        except Exception:
            return False

    def _api_headers(self) -> dict[str, str]:
        return {"X-ZAP-API-Key": self._api_key} if self._api_key else {}

    # ------------------------------------------------------------------
    # Outcomes
    # ------------------------------------------------------------------

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
                    check_code="zap.disabled",
                    category="security",
                    severity=Severity.INFO,
                    status=FindingStatus.NOT_APPLICABLE,
                    title="OWASP ZAP disabled by feature flag",
                    description=message,
                )
            ],
        )

    def _unavailable_outcome(self) -> ScanOutcome:
        return ScanOutcome(
            result=self._create_result(
                score=None,
                status="neutral",
                message="OWASP ZAP not available — skipped",
                recommendation=(
                    "Configure the sandbox Docker image "
                    "(SCANNER_DOCKER_IMAGE_ZAP) or a reachable ZAP sidecar."
                ),
            ),
            findings=[
                NormalizedFinding(
                    check_code="zap.unavailable",
                    category="security",
                    severity=Severity.INFO,
                    status=FindingStatus.NOT_APPLICABLE,
                    title="OWASP ZAP not available",
                    recommendation=(
                        "Configure the sandbox ZAP image or the REST sidecar."
                    ),
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
        """Legacy entry point; runs ZAP once via :meth:`execute`."""
        return self.execute(domain).findings

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
                        check_code="zap.target_validation",
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

        try:
            if self._transport == "docker":
                report, duration_ms = self._run_docker_scan(
                    target.url, timeout, context
                )
            else:
                report, duration_ms = self._run_api_scan(target.url, timeout, context)
        except SandboxError as exc:
            logger.error("ZAP sandbox unavailable: %s", exc)
            return ScanOutcome(
                result=self._create_result(
                    score=None,
                    status="warning",
                    message=f"ZAP could not be started safely: {exc}",
                ),
                findings=[
                    NormalizedFinding(
                        check_code="zap.sandbox_unavailable",
                        category="security",
                        severity=Severity.MEDIUM,
                        status=FindingStatus.UNKNOWN,
                        title="ZAP sandbox unavailable",
                        description=str(exc),
                    )
                ],
            )
        except Exception as exc:
            logger.exception("ZAP scan error: %s", exc)
            return ScanOutcome(
                result=self._create_result(
                    score=None,
                    status="warning",
                    message="ZAP scan failed",
                ),
                findings=[
                    NormalizedFinding(
                        check_code="zap.scan_error",
                        category="security",
                        severity=Severity.INFO,
                        status=FindingStatus.UNKNOWN,
                        title="ZAP scan failed",
                        description=str(exc)[:1000],
                    )
                ],
            )

        parsed = parse_zap_json(report)
        findings = self.normalize(parsed)
        high = [item for item in parsed if item.get("severity") in ("high", "critical")]
        medium = [item for item in parsed if item.get("severity") == "medium"]

        if high:
            status = "critical"
        elif medium:
            status = "warning"
        else:
            status = "neutral"

        return ScanOutcome(
            result=self._create_result(
                score=None,
                status=status,
                message=(
                    f"ZAP found {len(parsed)} alert(s), {len(high)} high/critical"
                ),
                duration_ms=duration_ms,
                transport=self._transport,
                total_alerts=len(parsed),
                high_alerts=len(high),
            ),
            findings=findings,
        )

    # ------------------------------------------------------------------
    # Docker sandbox transport
    # ------------------------------------------------------------------

    def _run_docker_scan(
        self,
        target_url: str,
        timeout: int,
        context: ScanContext | None,
    ) -> tuple[str, int]:
        executor = get_sandbox_executor()
        if executor.mode != SandboxMode.DOCKER:
            raise SandboxError(
                "ZAP docker transport requires SCANNER_SANDBOX_MODE=docker"
            )

        limits = (
            context.sandbox_limits
            if context is not None and context.sandbox_limits is not None
            else executor.limits_for(self.name, timeout=timeout)
        )

        # Docker resolves the bind source on the *host*, so the report
        # directory must live in a path both the worker and the daemon see.
        # ``SCANNER_SANDBOX_SHARED_WORK_DIR`` names that path explicitly;
        # TEMP/TMPDIR alone silently falls back to /tmp when the configured
        # directory is not writable, which makes ``docker run`` fail with
        # "bind source path does not exist".
        work_root = shared_work_dir()
        try:
            workdir = tempfile.mkdtemp(prefix="presence-zap-", dir=work_root or None)
        except OSError as exc:
            raise SandboxError(
                f"ZAP cannot create its report directory in {work_root or 'TEMP'}: {exc}"
            ) from exc
        # The ZAP image runs as an unprivileged, image-specific UID; the
        # directory is disposable and contains no secret.
        os.chmod(workdir, 0o777)
        report_path = os.path.join(workdir, "zap-report.json")

        try:
            script = str(self._cfg.get("script") or "zap-baseline.py")
            result = executor.run(
                # Clear the image entrypoint and invoke the baseline script
                # explicitly: ZAP tags differ (entrypoint vs. CMD), and this
                # keeps the command deterministic.
                command=[
                    script,
                    "-t",
                    target_url,
                    "-J",
                    "/zap/wrk/zap-report.json",
                    "-I",
                    # The automation framework prefixes file options with
                    # /zap/wrk a second time and then fails to write the
                    # report; use the classic baseline flow instead.
                    "--autooff",
                ],
                limits=limits,
                scanner_name=self.name,
                docker_image=self._docker_image,
                docker_entrypoint="",
                # The baseline script refuses file options unless /zap/wrk is
                # a mount point.  Mounting the host workdir there also avoids
                # a duplicate mount with the configured /zap/wrk tmpfs.
                mounts=[(workdir, "/zap/wrk")],
                docker_tmpfs=[],
                # The official zap-stable image writes ``zap.out`` under /zap
                # and its configuration under /home/zap; a read-only root
                # filesystem makes the baseline script abort before ZAP
                # starts.  The container remains one-shot, capability-free
                # and limited to the validated /zap/wrk bind mount.
                read_only=False,
                env_extra={"HOME": "/tmp"},
            )

            if result.timed_out or result.memory_exceeded:
                raise SandboxError(
                    "ZAP was stopped by the sandbox "
                    f"({'timeout' if result.timed_out else 'memory limit'})"
                )

            report = ""
            if os.path.isfile(report_path):
                with open(
                    report_path, "r", encoding="utf-8", errors="replace"
                ) as handle:
                    report = handle.read()

            # Custom images may print the JSON report to stdout instead of
            # writing the mounted file.
            if not report.strip() and result.stdout.lstrip().startswith("{"):
                report = result.stdout

            if not report.strip():
                raise SandboxError(
                    "ZAP produced no JSON report "
                    f"(exit={result.exit_code}, stderr={result.stderr[:300]!r})"
                )
            if result.exit_code not in (0, 1, 2):
                logger.warning(
                    "ZAP exited with code %s (report still parsed)", result.exit_code
                )

            return report, result.duration_ms
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # REST sidecar transport
    # ------------------------------------------------------------------

    def _run_api_scan(
        self,
        target_url: str,
        timeout: int,
        context: ScanContext | None,
    ) -> tuple[str, int]:
        deadline = time.monotonic() + timeout
        if context is not None:
            deadline = min(deadline, context.deadline_monotonic)

        started = time.monotonic()
        session = http_requests.Session()
        session.headers.update(self._api_headers())
        base = self._api_url

        try:
            spider = session.get(
                f"{base}/JSON/spider/action/scan/",
                params={"url": target_url, "maxChildren": "5"},
                timeout=(5, 30),
            )
            if spider.ok:
                spider_id = str(spider.json().get("scan", "0"))
                self._wait_for_scan(
                    session,
                    f"{base}/JSON/spider/view/status/",
                    {"scanId": spider_id},
                    deadline,
                )

            if bool(self._cfg.get("active_scan", False)):
                active = session.get(
                    f"{base}/JSON/ascan/action/scan/",
                    params={"url": target_url, "recurse": "true"},
                    timeout=(5, 30),
                )
                if active.ok:
                    scan_id = str(active.json().get("scan", "0"))
                    self._wait_for_scan(
                        session,
                        f"{base}/JSON/ascan/view/status/",
                        {"scanId": scan_id},
                        deadline,
                    )

            alerts = session.get(
                f"{base}/JSON/core/view/alerts/",
                params={"baseurl": target_url},
                timeout=(5, 30),
            )
            alerts.raise_for_status()
            return alerts.text, int((time.monotonic() - started) * 1000)
        finally:
            session.close()

    @staticmethod
    def _wait_for_scan(
        session: http_requests.Session,
        status_url: str,
        params: dict[str, str],
        deadline: float,
        poll_interval: float = 3.0,
    ) -> None:
        while time.monotonic() < deadline:
            try:
                response = session.get(status_url, params=params, timeout=(3, 10))
                if response.ok and str(response.json().get("status", "0")) == "100":
                    return
            except Exception:
                pass
            time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))

    # ------------------------------------------------------------------
    # Parsing / normalization
    # ------------------------------------------------------------------

    def parse(self, output: str) -> list[dict[str, Any]]:
        return parse_zap_json(output)

    def normalize(
        self, parsed_results: list[dict[str, Any]]
    ) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        seen: set[tuple[str, str]] = set()

        for item in parsed_results:
            sev_raw = str(item.get("severity", "info")).lower()
            severity = _ZAP_SEVERITY_MAP.get(sev_raw, Severity.INFO)
            status = (
                FindingStatus.FAIL
                if sev_raw in ("high", "critical")
                else FindingStatus.WARNING
            )

            alert_id = str(item.get("alert_id") or "unknown")
            instances = item.get("instances") or []
            matched_url = ""
            if isinstance(instances, list) and instances:
                first = instances[0]
                if isinstance(first, dict):
                    matched_url = str(first.get("uri", "") or "")

            key = (alert_id, matched_url)
            if key in seen:
                continue
            seen.add(key)

            cwe = str(item.get("cweid", "") or "")
            reference = _first_reference_url(str(item.get("reference", "") or ""))
            if not reference and cwe:
                reference = f"https://cwe.mitre.org/data/definitions/{cwe}.html"

            findings.append(
                NormalizedFinding(
                    check_code=f"zap.alert.{alert_id}"[:128],
                    category="security",
                    severity=severity,
                    status=status,
                    title=str(item.get("name") or "ZAP Alert")[:255],
                    description=str(item.get("description", ""))[:4000],
                    evidence={
                        "alert_id": alert_id,
                        "confidence": item.get("confidence", ""),
                        "riskcode": item.get("riskcode", ""),
                        "wascid": item.get("wascid", ""),
                        "cweid": cwe,
                        "matched_url": matched_url,
                        "instances": instances[:5],
                    },
                    recommendation=str(item.get("solution", ""))[:2000],
                    reference_url=reference,
                )
            )

        return findings


zap_scanner = ZAPScanner()
