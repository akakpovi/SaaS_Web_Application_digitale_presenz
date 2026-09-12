"""OWASP ZAP adapter (REST API mode).

ZAP is operated via its REST API rather than CLI stdout, since the daemon
mode provides better control.  The adapter starts/connects to ZAP and
triggers an active/spider scan.

For Docker-based deployment, ZAP runs as a sidecar service.
"""

from __future__ import annotations

import logging
import shutil
import time
from typing import Any

import requests as http_requests

from django.conf import settings

from scanners.base import BaseScanner, NormalizedFinding, Severity, FindingStatus, ScanResult, ScannerType
from scanners.exceptions import TargetValidationError
from scanners.parsers.zap import parse_zap_json
from scanners.security.target_validator import validate_target

logger = logging.getLogger(__name__)

_ZAP_SEVERITY_MAP = {
    "informational": Severity.INFO,
    "low": Severity.LOW,
    "medium": Severity.MEDIUM,
    "high": Severity.HIGH,
}


class ZAPScanner(BaseScanner):
    """OWASP ZAP scanner adapter (REST API mode)."""

    name = "zap"
    scanner_type = ScannerType.API
    _binary = None  # ZAP is API-based

    @property
    def timeout(self) -> int:  # type: ignore[override]
        cfg = getattr(settings, "SCANNER_CONFIG", {})
        return cfg.get("zap", {}).get("timeout", 300)

    @property
    def _zap_api_url(self) -> str:
        cfg = getattr(settings, "SCANNER_CONFIG", {}).get("zap", {})
        return cfg.get("api_url", "http://localhost:8090")

    @property
    def _zap_api_key(self) -> str:
        cfg = getattr(settings, "SCANNER_CONFIG", {}).get("zap", {})
        return cfg.get("api_key", "")

    def is_available(self) -> bool:
        """Check if ZAP REST API is accessible."""
        try:
            resp = http_requests.get(
                f"{self._zap_api_url}/JSON/core/view/version/",
                params={"apikey": self._zap_api_key},
                timeout=3,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def scan(self, domain: str) -> ScanResult:
        if not self.is_available():
            return self._create_result(
                score=None,
                status="neutral",
                message="OWASP ZAP not available — skipped",
                recommendation="Configure ZAP sidecar service for active scanning.",
            )

        try:
            target_info = validate_target(f"https://{domain}")
        except TargetValidationError as exc:
            return self._create_result(score=None, status="critical", message=str(exc))

        report = self._run_zap_scan(target_info.url)
        findings = parse_zap_json(report)
        high = [f for f in findings if f.get("severity") in ("high", "critical")]

        return self._create_result(
            score=None,
            status="critical" if high else "neutral",
            message=f"ZAP found {len(findings)} alert(s), {len(high)} high/critical",
            total_alerts=len(findings),
            high_alerts=len(high),
        )

    def scan_findings(self, domain: str) -> list[NormalizedFinding]:
        if not self.is_available():
            return [NormalizedFinding(
                check_code="zap.unavailable",
                category="security",
                severity=Severity.INFO,
                status=FindingStatus.NOT_APPLICABLE,
                title="OWASP ZAP not available",
                description="Configure the ZAP sidecar service to enable active web scanning.",
                recommendation="Add the zap-scanner service to docker-compose.yml.",
            )]

        try:
            target_info = validate_target(f"https://{domain}")
        except TargetValidationError as exc:
            return [NormalizedFinding(
                check_code="zap.target_validation",
                category="security",
                severity=Severity.HIGH,
                status=FindingStatus.FAIL,
                title="Target validation failed",
                description=str(exc),
            )]

        report = self._run_zap_scan(target_info.url)
        parsed = parse_zap_json(report)
        return self.normalize(parsed)

    def build_command(self, target: str, options: dict | None = None) -> list[str]:
        raise NotImplementedError("ZAP uses REST API mode — use scan_findings() directly")

    def parse(self, output: str) -> list[dict[str, Any]]:
        return parse_zap_json(output)

    def normalize(self, parsed_results: list[dict[str, Any]]) -> list[NormalizedFinding]:
        findings: list[NormalizedFinding] = []
        for item in parsed_results:
            sev_raw = item.get("severity", "informational").lower()
            severity = _ZAP_SEVERITY_MAP.get(sev_raw, Severity.INFO)
            status = FindingStatus.FAIL if sev_raw in ("high", "critical") else FindingStatus.WARNING

            cwe = item.get("cweid", "")
            ref_url = f"https://cwe.mitre.org/data/definitions/{cwe}.html" if cwe else ""

            findings.append(NormalizedFinding(
                check_code=f"zap.alert.{item.get('alert_id', 'unknown')}",
                category="security",
                severity=severity,
                status=status,
                title=item.get("name", "ZAP Alert"),
                description=item.get("description", ""),
                evidence={
                    "instances": item.get("instances", [])[:5],
                    "wascid": item.get("wascid", ""),
                },
                recommendation=item.get("solution", ""),
                reference_url=ref_url,
            ))

        return findings

    def _run_zap_scan(self, target_url: str) -> str:
        """Run ZAP spider + active scan and return JSON report."""
        params = {"apikey": self._zap_api_key}
        base = self._zap_api_url
        timeout = self.timeout

        try:
            # Spider scan
            spider_resp = http_requests.get(
                f"{base}/JSON/spider/action/scan/",
                params={**params, "url": target_url, "maxChildren": "5"},
                timeout=30,
            )
            if spider_resp.ok:
                spider_id = spider_resp.json().get("scan", "0")
                self._wait_for_scan(
                    f"{base}/JSON/spider/view/status/",
                    params={**params, "scanId": spider_id},
                    timeout=min(60, timeout // 2),
                )

            # Active scan
            active_resp = http_requests.get(
                f"{base}/JSON/ascan/action/scan/",
                params={**params, "url": target_url, "recurse": "true"},
                timeout=30,
            )
            if active_resp.ok:
                scan_id = active_resp.json().get("scan", "0")
                self._wait_for_scan(
                    f"{base}/JSON/ascan/view/status/",
                    params={**params, "scanId": scan_id},
                    timeout=timeout,
                )

            # Fetch JSON report
            report_resp = http_requests.get(
                f"{base}/JSON/core/view/alerts/",
                params={**params, "baseurl": target_url},
                timeout=30,
            )
            if report_resp.ok:
                return report_resp.text

        except Exception as exc:
            logger.warning("ZAP scan error: %s", exc)

        return ""

    def _wait_for_scan(
        self, status_url: str, params: dict, timeout: int, poll_interval: float = 5.0
    ) -> None:
        """Poll ZAP scan status until 100% or timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                resp = http_requests.get(status_url, params=params, timeout=10)
                if resp.ok and str(resp.json().get("status", "0")) == "100":
                    return
            except Exception:
                pass
            time.sleep(poll_interval)


zap_scanner = ZAPScanner()
