"""Scan Orchestrator — the core of the Scanner Engine.

Orchestrates the execution of multiple scanners for a given scan, tracking
progress, creating ScannerRun/Finding records, and updating the scan state.

Architecture principles
-----------------------
* One ``ScannerRun`` per scanner per scan.
* Findings are normalised and stored independently of CheckResults.
* CheckResults are still populated for backward compatibility with the
  existing health score engine.
* The orchestrator is scanner-agnostic — it uses the ScannerRegistry.
* A single scanner failure does NOT fail the entire scan.
* Progress is updated in real-time via Scan.steps.

Scan lifecycle
--------------
PENDING → QUEUED (transition handled outside orchestrator, before task dispatch)
QUEUED → RUNNING (orchestrator takes ownership here)
RUNNING → COMPLETED | FAILED | CANCELLED

Usage::

    orchestrator = ScanOrchestrator(scan_id=42)
    orchestrator.run()
"""

from __future__ import annotations

import logging
import time
from typing import Any

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class ScanOrchestrator:
    """Orchestrates scanner execution for a given scan."""

    def __init__(self, scan_id: int) -> None:
        self.scan_id = scan_id

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Execute the full scan lifecycle.

        Called by the Celery task.  Exceptions that escape this method are
        caught by the Celery task itself and result in the scan being marked
        FAILED.
        """
        from scans.models import Scan
        from scans.services.scoring import recalculate_scan_health
        from scans.services.steps_builder import build_initial_steps

        scan = self._load_scan()
        if scan is None:
            return

        # Idempotency guard: don't re-run a completed/failed/cancelled scan.
        if scan.status in (Scan.Status.COMPLETED, Scan.Status.FAILED, Scan.Status.CANCELLED):
            logger.info(
                "ScanOrchestrator: Scan %d is already %s — skipping",
                self.scan_id,
                scan.status,
            )
            return

        domain = scan.website.domain

        # Initialise steps list for this scan type.
        steps = build_initial_steps(scan.scan_type)
        scan.steps = steps
        scan.progress = 0
        scan.current_step = ""
        scan.save(update_fields=["steps", "progress", "current_step", "updated_at"])

        # QUEUED → RUNNING
        try:
            scan.transition_to(Scan.Status.RUNNING)
        except Exception as exc:
            logger.error(
                "ScanOrchestrator: Cannot transition scan %d to RUNNING: %s",
                self.scan_id,
                exc,
            )
            return

        # ── Run all scanner steps ──────────────────────────────────────
        try:
            self._run_all_steps(scan, domain, steps)
        except Exception as exc:
            logger.exception(
                "ScanOrchestrator: Unexpected error for scan %d", self.scan_id
            )
            try:
                scan.transition_to(Scan.Status.FAILED, failure_message=str(exc)[:500])
            except Exception:
                pass
            return

        # ── Check if cancelled during steps ────────────────────────────
        scan.refresh_from_db(fields=["status"])
        if scan.status == Scan.Status.CANCELLED:
            logger.info("ScanOrchestrator: Scan %d cancelled. Stopping.", self.scan_id)
            return

        # ── Recalculate health score ───────────────────────────────────
        try:
            recalculate_scan_health(scan)
        except Exception as exc:
            logger.error(
                "ScanOrchestrator: Failed to recalculate health for scan %d: %s",
                self.scan_id,
                exc,
            )

        # ── Finalise ──────────────────────────────────────────────────
        scan.progress = 100
        scan.current_step = ""
        scan.save(update_fields=["progress", "current_step", "updated_at"])
        scan.transition_to(Scan.Status.COMPLETED)
        logger.info("ScanOrchestrator: Scan %d completed successfully", self.scan_id)

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    def _run_all_steps(
        self,
        scan: Any,
        domain: str,
        steps: list[dict[str, Any]],
    ) -> None:
        """Iterate through all steps, running each scanner in order."""
        from scanners.registry import ScannerRegistry
        from scans.models import Scan
        from scans.services.steps_builder import compute_overall_progress, StepStatus

        for step in steps:
            key = step["key"]
            scanner_name = step["scanner"]

            # ── Check for cancellation before every step ───────────────
            scan.refresh_from_db(fields=["status"])
            if scan.status == Scan.Status.CANCELLED:
                logger.info(
                    "ScanOrchestrator: Scan %d was cancelled — stopping at step '%s'",
                    self.scan_id,
                    key,
                )
                # Mark remaining pending steps as cancelled.
                for remaining in steps:
                    if remaining.get("status") == StepStatus.PENDING:
                        remaining["status"] = StepStatus.SKIPPED
                scan.steps = steps
                scan.save(update_fields=["steps", "updated_at"])
                return

            # ── Mark step as running ───────────────────────────────────
            step["status"] = StepStatus.RUNNING
            step["progress"] = 0
            scan.current_step = step["label"]
            scan.steps = steps
            scan.progress = compute_overall_progress(steps)
            scan.save(update_fields=["steps", "current_step", "progress", "updated_at"])

            # ── Resolve scanner from registry ──────────────────────────
            try:
                scanner = ScannerRegistry.get(scanner_name)
            except KeyError:
                logger.warning(
                    "ScanOrchestrator: Scanner '%s' not in registry — skipping step '%s'",
                    scanner_name,
                    key,
                )
                step["status"] = StepStatus.SKIPPED
                step["progress"] = 100
                step["error"] = f"Scanner '{scanner_name}' not registered"
                self._flush_step(scan, steps)
                continue

            # ── Run the scanner ────────────────────────────────────────
            step_start = time.monotonic()
            scanner_run = self._create_scanner_run(scan, scanner_name)
            scanner_run.start()

            try:
                step["progress"] = 10
                self._flush_step(scan, steps)

                # Use settings-based timeout if the scanner uses a property.
                scanner_cfg = self._scanner_cfg(scanner_name)
                timeout = scanner_cfg.get("timeout", scanner.timeout)

                # Check availability (external tools may not be installed).
                if not scanner.is_available():
                    raise ScannerUnavailable(
                        f"Scanner '{scanner_name}' binary not found on PATH"
                    )

                # Run scanners with SSRF-validated target.
                scan_result = scanner.scan(domain)
                step["progress"] = 50

                # Get granular normalized findings.
                findings = scanner.scan_findings(domain)
                step["progress"] = 80

                # Persist findings to DB.
                self._persist_findings(scanner_run, findings)

                # Persist CheckResult (backward compat with health score engine).
                self._persist_check_result(scan, scanner_name, scan_result)

                duration_ms = int((time.monotonic() - step_start) * 1000)
                scanner_run.finish(
                    status="completed",
                    metadata={
                        "findings_count": len(findings),
                        "scanner_status": scan_result.status,
                        "score": scan_result.score,
                    },
                    duration_ms=duration_ms,
                )
                step["status"] = StepStatus.COMPLETED
                step["progress"] = 100
                step["duration_ms"] = duration_ms

            except ScannerUnavailable as exc:
                duration_ms = int((time.monotonic() - step_start) * 1000)
                logger.info(
                    "ScanOrchestrator: Scanner '%s' unavailable for scan %d: %s",
                    scanner_name,
                    self.scan_id,
                    exc,
                )
                scanner_run.finish(
                    status="unavailable",
                    error_message=str(exc)[:500],
                    duration_ms=duration_ms,
                )
                step["status"] = StepStatus.UNAVAILABLE
                step["progress"] = 100
                step["duration_ms"] = duration_ms
                step["error"] = str(exc)
                # Not an error — gracefully continue.

            except Exception as exc:
                duration_ms = int((time.monotonic() - step_start) * 1000)
                error_msg = str(exc)[:500]
                logger.exception(
                    "ScanOrchestrator: Scanner '%s' failed for scan %d: %s",
                    scanner_name,
                    self.scan_id,
                    error_msg,
                )
                scanner_run.finish(
                    status="failed",
                    error_message=error_msg,
                    duration_ms=duration_ms,
                )
                step["status"] = StepStatus.FAILED
                step["progress"] = 100
                step["duration_ms"] = duration_ms
                step["error"] = error_msg
                # Do NOT re-raise — one scanner failure should not abort the scan.

            self._flush_step(scan, steps)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_scan(self) -> Any | None:
        from scans.models import Scan

        try:
            return Scan.objects.select_related("website").get(pk=self.scan_id)
        except Scan.DoesNotExist:
            logger.error(
                "ScanOrchestrator: Scan %d not found", self.scan_id
            )
            return None

    def _scanner_cfg(self, name: str) -> dict:
        """Return per-scanner settings from SCANNER_CONFIG."""
        return getattr(settings, "SCANNER_CONFIG", {}).get(name, {})

    def _flush_step(self, scan: Any, steps: list[dict]) -> None:
        """Persist step progress and recompute overall progress."""
        from scans.services.steps_builder import compute_overall_progress

        scan.steps = steps
        scan.progress = compute_overall_progress(steps)
        scan.save(update_fields=["steps", "progress", "updated_at"])

    def _create_scanner_run(self, scan: Any, scanner_name: str) -> Any:
        from scans.models import ScannerRun

        return ScannerRun.objects.create(
            scan=scan,
            scanner=scanner_name,
            status=ScannerRun.Status.PENDING,
        )

    def _persist_findings(self, scanner_run: Any, findings: list) -> None:
        """Bulk-create Finding records from NormalizedFinding instances."""
        from scans.models import Finding

        if not findings:
            return

        max_raw = getattr(settings, "SCANNER_MAX_RAW_OUTPUT", 50_000)

        finding_objs = []
        for f in findings:
            # Coerce reference_url to a safe value (no None, not too long).
            ref_url = (f.reference_url or "")[:500]

            finding_objs.append(Finding(
                scanner_run=scanner_run,
                category=f.category[:32],
                check_code=f.check_code[:128],
                title=f.title[:255],
                description=f.description or "",
                severity=f.severity,
                status=f.status,
                evidence=f.evidence if isinstance(f.evidence, dict) else {},
                detected_value=f.detected_value,
                expected_value=f.expected_value,
                recommendation=f.recommendation or "",
                reference_url=ref_url,
                duration_ms=f.duration_ms if f.duration_ms else None,
            ))

        Finding.objects.bulk_create(finding_objs, ignore_conflicts=True)
        logger.debug(
            "ScanOrchestrator: Persisted %d finding(s) for scanner_run %d",
            len(finding_objs),
            scanner_run.pk,
        )

    def _persist_check_result(
        self, scan: Any, scanner_name: str, scan_result: Any
    ) -> None:
        """Create/update a CheckResult from a ScanResult.

        This bridge keeps the existing health score engine working with the
        new scanner pipeline.  External security scanners (nmap, nikto, etc.)
        do NOT map to CheckResult categories and are silently ignored here.
        """
        from scans.models import CheckResult

        # Map scanner name → CheckResult category.
        _CATEGORY_MAP: dict[str, str] = {
            "website":          CheckResult.Category.WEBSITE,
            "ssl":              CheckResult.Category.SSL,
            "dns":              CheckResult.Category.DNS,
            "email_security":   CheckResult.Category.EMAIL_SECURITY,
            "security_headers": CheckResult.Category.SECURITY_HEADERS,
            "performance":      CheckResult.Category.PERFORMANCE,
            "uptime":           CheckResult.Category.UPTIME,
        }

        category = _CATEGORY_MAP.get(scanner_name)
        if category is None:
            # External scanners (nmap, nikto, etc.) — skip.
            return

        # Uptime results are not scored.
        is_uptime = category == CheckResult.Category.UPTIME
        score = None if is_uptime else scan_result.score

        try:
            CheckResult.objects.update_or_create(
                scan=scan,
                category=category,
                defaults={
                    "status": scan_result.status,
                    "score": score,
                    "summary": (scan_result.message or "")[:2000],
                    "recommendation": (scan_result.recommendation or "")[:2000],
                    "technical_details": scan_result.details or {},
                },
            )
        except Exception as exc:
            logger.error(
                "ScanOrchestrator: Failed to persist CheckResult for %s: %s",
                scanner_name,
                exc,
            )


class ScannerUnavailable(Exception):
    """Raised when a scanner's binary is not installed."""
