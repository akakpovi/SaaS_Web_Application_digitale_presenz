"""Automatic ingestion of scanner runs into ``SecurityFinding``.

These tests cover the bridge that makes the automated flow work: a completed
ZAP/Nuclei run must update the tenant's long-lived findings without any manual
import, and an incomplete run (sandbox timeout) must never close the findings
it did not report.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from accounts.models import User
from advisory.models import SecurityFinding
from advisory.services.scan_ingestion import (
    ingest_scan_findings,
    parsed_report_for,
)
from scans.models import Scan, ScannerRun
from scanners.base import FindingStatus, NormalizedFinding, Severity
from websites.models import Website


def normalized(
    *,
    title: str,
    severity: str = Severity.HIGH,
    check_code: str = "nuclei.exposed-env-file",
    description: str = "The file is publicly readable.",
    evidence: dict | None = None,
    recommendation: str = "",
) -> NormalizedFinding:
    return NormalizedFinding(
        check_code=check_code,
        category="security",
        severity=severity,
        status=FindingStatus.FAIL,
        title=title,
        description=description,
        evidence=evidence
        if evidence is not None
        else {"template_id": "exposed-env-file", "matched_at": "https://a/.env"},
        recommendation=recommendation,
        reference_url="https://docs.example/env",
    )


class ScanIngestionMappingTests(TestCase):
    def test_normalized_findings_are_mapped_to_parsed_findings(self):
        report = parsed_report_for(
            "nuclei",
            [
                normalized(
                    title="Exposed .env File",
                    severity=Severity.CRITICAL,
                    recommendation="Block dotfiles at the web server.",
                )
            ],
        )

        self.assertEqual(report.source, "nuclei")
        self.assertEqual(len(report.findings), 1)
        finding = report.findings[0]
        self.assertEqual(finding.vulnerability_name, "Exposed .env File")
        self.assertEqual(finding.severity, "critical")
        self.assertIn("publicly readable", finding.description)
        self.assertIn("Recommendation: Block dotfiles", finding.description)
        self.assertIn("check: nuclei.exposed-env-file", finding.proof_or_payload)
        self.assertIn("matched_at", finding.proof_or_payload)
        self.assertIn("reference: https://docs.example/env", finding.proof_or_payload)

    def test_same_title_is_collapsed_inside_one_run(self):
        report = parsed_report_for(
            "nuclei",
            [
                normalized(title="Exposed .env File", evidence={"url": "https://a/.env"}),
                normalized(title="Exposed .env File", evidence={"url": "https://b/.env"}),
            ],
        )
        self.assertEqual(len(report.findings), 1)
        self.assertIn("https://a/.env", report.findings[0].proof_or_payload)
        self.assertIn("https://b/.env", report.findings[0].proof_or_payload)

    def test_unknown_severity_falls_back_to_info(self):
        report = parsed_report_for("zap", [normalized(title="Odd", severity="weird")])
        self.assertEqual(report.findings[0].severity, "info")


class ScanIngestionServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            email="auto-ingest@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(owner=self.owner, domain="auto.example")
        self.organization = self.website.organization
        self.scan = Scan.objects.create(
            website=self.website,
            scan_type=Scan.ScanType.SECURITY,
            status=Scan.Status.RUNNING,
        )
        ScannerRun.objects.create(scan=self.scan, scanner="nuclei")

        self.other_owner = User.objects.create_user(
            email="auto-ingest-other@example.com", password="pass1234!"
        )
        self.other_website = Website.objects.create(
            owner=self.other_owner, domain="auto-other.example"
        )
        self.other_org = self.other_website.organization

    def findings(self, **filters):
        return SecurityFinding.objects.filter(
            organization=self.organization, asset=self.website, **filters
        )

    def test_completed_run_creates_findings(self):
        outcome = ingest_scan_findings(
            scan=self.scan,
            scanner_name="nuclei",
            findings=[normalized(title="Exposed .env File")],
        )

        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.source, "nuclei")
        self.assertEqual(outcome.created, 1)
        finding = self.findings().get()
        self.assertEqual(finding.vulnerability_name, "Exposed .env File")
        self.assertEqual(finding.status, SecurityFinding.Status.OPEN)
        self.assertEqual(finding.severity, "high")

    def test_replaying_the_same_run_updates_instead_of_duplicating(self):
        payload = [normalized(title="Exposed .env File")]
        ingest_scan_findings(scan=self.scan, scanner_name="nuclei", findings=payload)
        second = ingest_scan_findings(
            scan=self.scan, scanner_name="nuclei", findings=payload
        )

        self.assertEqual(second.created, 0)
        self.assertEqual(second.updated, 1)
        self.assertEqual(self.findings().count(), 1)

    def test_absent_findings_are_resolved_on_a_complete_run(self):
        ingest_scan_findings(
            scan=self.scan,
            scanner_name="nuclei",
            findings=[
                normalized(title="Exposed .env File"),
                normalized(title="Deprecated TLS", check_code="nuclei.tls-old"),
            ],
        )

        outcome = ingest_scan_findings(
            scan=self.scan,
            scanner_name="nuclei",
            findings=[normalized(title="Exposed .env File")],
        )

        self.assertEqual(outcome.resolved, 1)
        self.assertEqual(
            self.findings(status=SecurityFinding.Status.RESOLVED).values_list(
                "vulnerability_name", flat=True
            ).get(),
            "Deprecated TLS",
        )

    def test_partial_run_never_resolves_missing_findings(self):
        ingest_scan_findings(
            scan=self.scan,
            scanner_name="nuclei",
            findings=[
                normalized(title="Exposed .env File"),
                normalized(title="Deprecated TLS", check_code="nuclei.tls-old"),
            ],
        )

        outcome = ingest_scan_findings(
            scan=self.scan,
            scanner_name="nuclei",
            findings=[normalized(title="Exposed .env File")],
            complete=False,
        )

        self.assertEqual(outcome.resolved, 0)
        self.assertEqual(
            self.findings(status=SecurityFinding.Status.OPEN).count(), 2
        )

    def test_partial_meta_does_not_hide_real_findings_and_never_resolves(self):
        ingest_scan_findings(
            scan=self.scan,
            scanner_name="nuclei",
            findings=[
                normalized(title="Exposed .env File"),
                normalized(title="Deprecated TLS", check_code="nuclei.tls-old"),
            ],
        )

        timeout = NormalizedFinding(
            check_code="nuclei.timeout",
            category="security",
            severity=Severity.INFO,
            status=FindingStatus.UNKNOWN,
            title="Nuclei stopped by the sandbox (timeout)",
        )
        outcome = ingest_scan_findings(
            scan=self.scan,
            scanner_name="nuclei",
            findings=[timeout, normalized(title="Exposed .env File")],
            complete=True,  # adapter meta must force non-resolving ingest
        )

        self.assertEqual(outcome.resolved, 0)
        self.assertEqual(outcome.updated, 1)
        self.assertEqual(
            self.findings(status=SecurityFinding.Status.OPEN).count(), 2
        )
        self.assertFalse(self.findings(vulnerability_name__icontains="timeout").exists())

    def test_output_truncated_meta_forces_non_resolving_ingest(self):
        ingest_scan_findings(
            scan=self.scan,
            scanner_name="nuclei",
            findings=[
                normalized(title="Exposed .env File"),
                normalized(title="Deprecated TLS", check_code="nuclei.tls-old"),
            ],
        )

        truncated = NormalizedFinding(
            check_code="nuclei.output_truncated",
            category="security",
            severity=Severity.INFO,
            status=FindingStatus.UNKNOWN,
            title="Nuclei output was truncated",
        )
        outcome = ingest_scan_findings(
            scan=self.scan,
            scanner_name="nuclei",
            findings=[truncated, normalized(title="Exposed .env File")],
            complete=True,
        )

        self.assertEqual(outcome.resolved, 0)
        self.assertEqual(
            self.findings(status=SecurityFinding.Status.OPEN).count(), 2
        )
        self.assertFalse(
            self.findings(vulnerability_name__icontains="truncated").exists()
        )

    def test_clean_empty_complete_report_resolves_old_findings(self):
        ingest_scan_findings(
            scan=self.scan,
            scanner_name="nuclei",
            findings=[normalized(title="Exposed .env File")],
        )

        outcome = ingest_scan_findings(
            scan=self.scan,
            scanner_name="nuclei",
            findings=[],
            complete=True,
        )

        self.assertEqual(outcome.resolved, 1)
        self.assertEqual(self.findings(status=SecurityFinding.Status.OPEN).count(), 0)

    def test_tool_failure_never_touches_existing_findings(self):
        """A ZAP sandbox failure must not resolve the real findings.

        The adapter emits one ``zap.sandbox_unavailable`` finding and no real
        report in that case; ingesting it would create a phantom finding and
        close every genuine one.
        """
        ingest_scan_findings(
            scan=self.scan,
            scanner_name="zap",
            findings=[
                normalized(title="Missing CSP", check_code="zap.missing-csp"),
                normalized(title="X-Frame-Options", check_code="zap.xfo"),
            ],
        )
        before = dict(
            self.findings().values_list("vulnerability_name", "status")
        )

        failure = NormalizedFinding(
            check_code="zap.sandbox_unavailable",
            category="security",
            severity=Severity.MEDIUM,
            status=FindingStatus.UNKNOWN,
            title="ZAP sandbox unavailable",
            description="docker: invalid mount config",
        )
        outcome = ingest_scan_findings(
            scan=self.scan,
            scanner_name="zap",
            findings=[failure],
            complete=True,
        )

        self.assertIsNone(outcome)
        after = dict(
            self.findings().values_list("vulnerability_name", "status")
        )
        self.assertEqual(before, after)
        self.assertEqual(self.findings().count(), 2)
        self.assertFalse(
            self.findings(vulnerability_name="ZAP sandbox unavailable").exists()
        )

    def test_health_scanners_are_not_ingested(self):
        self.assertIsNone(
            ingest_scan_findings(
                scan=self.scan,
                scanner_name="ssl",
                findings=[normalized(title="Certificate", check_code="ssl.expiry")],
            )
        )
        self.assertEqual(self.findings().count(), 0)

    def test_guest_scans_are_not_ingested(self):
        guest = Website.objects.create(domain="guest-auto.example", is_guest=True)
        guest_scan = Scan.objects.create(
            website=guest, scan_type=Scan.ScanType.SECURITY, is_guest=True
        )
        self.assertIsNone(
            ingest_scan_findings(
                scan=guest_scan,
                scanner_name="zap",
                findings=[normalized(title="XSS")],
            )
        )
        self.assertEqual(SecurityFinding.objects.filter(asset=guest).count(), 0)

    def test_other_tenants_findings_are_untouched(self):
        SecurityFinding.objects.create(
            organization=self.other_org,
            asset=self.other_website,
            scanner_source="nuclei",
            vulnerability_name="Exposed .env File",
            severity=SecurityFinding.Severity.HIGH,
        )

        ingest_scan_findings(
            scan=self.scan,
            scanner_name="nuclei",
            findings=[normalized(title="Something else")],
            complete=True,
        )

        other = SecurityFinding.objects.get(organization=self.other_org)
        self.assertEqual(other.status, SecurityFinding.Status.OPEN)


class OrchestratorIngestionHookTests(TestCase):
    """The hook must never fail a scan, even when ingestion raises."""

    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            email="hook@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(owner=self.owner, domain="hook.example")
        self.scan = Scan.objects.create(
            website=self.website,
            scan_type=Scan.ScanType.SECURITY,
            status=Scan.Status.RUNNING,
        )

    def _orchestrator(self):
        from scans.services.orchestrator import ScanOrchestrator

        return ScanOrchestrator(scan_id=self.scan.pk)

    def test_ingestion_exception_is_swallowed(self):
        orchestrator = self._orchestrator()
        with patch(
            "advisory.services.scan_ingestion.ingest_scan_findings",
            side_effect=RuntimeError("database down"),
        ):
            # A broken ingestion must not propagate: the scan already succeeded.
            orchestrator._ingest_security_findings(
                self.scan,
                "nuclei",
                [normalized(title="Exposed .env File")],
                SimpleNamespace(details={}),
            )

        self.assertFalse(
            SecurityFinding.objects.filter(organization=self.website.organization).exists()
        )

    def test_timeout_details_disable_resolution(self):
        orchestrator = self._orchestrator()
        with patch(
            "advisory.services.scan_ingestion.ingest_scan_findings",
            return_value=None,
        ) as ingest:
            orchestrator._ingest_security_findings(
                self.scan,
                "nuclei",
                [],
                SimpleNamespace(details={"timed_out": True}),
            )

        self.assertFalse(ingest.call_args.kwargs["complete"])

    def test_narrow_profile_disables_resolution(self):
        orchestrator = self._orchestrator()
        with patch(
            "advisory.services.scan_ingestion.ingest_scan_findings",
            return_value=None,
        ) as ingest:
            orchestrator._ingest_security_findings(
                self.scan,
                "nuclei",
                [],
                SimpleNamespace(
                    details={"scan_complete": True, "resolve_missing": False}
                ),
            )

        self.assertFalse(ingest.call_args.kwargs["complete"])
