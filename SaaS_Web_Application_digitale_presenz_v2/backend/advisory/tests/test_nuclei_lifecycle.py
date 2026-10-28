"""End-to-end-ish lifecycle of Nuclei findings through the ingestion service.

These tests deliberately start from real Nuclei JSONL and run the adapter's
``parse``/``normalize`` methods before calling ``ingest_scan_findings``.  That
covers the bridge that unit tests of either side can miss: a valid report must
create/update the tenant's ``SecurityFinding`` rows, a replay must not
duplicate them, and only a complete run may resolve a missing row.
"""

from __future__ import annotations

import json

from django.test import TestCase

from accounts.models import User
from advisory.models import SecurityFinding
from advisory.services.scan_ingestion import ingest_scan_findings
from scans.models import Scan
from scanners.base import FindingStatus, NormalizedFinding, Severity
from scanners.implementations.nuclei import NucleiScanner
from websites.models import Website


def _jsonl(*entries: dict) -> str:
    return "\n".join(json.dumps(entry) for entry in entries)


def _entry(template_id: str, name: str, severity: str = "high") -> dict:
    return {
        "template-id": template_id,
        "info": {
            "name": name,
            "severity": severity,
            "description": f"{name} was detected.",
            "tags": ["exposure"],
        },
        "matched-at": f"https://lifecycle.example/{template_id}",
        "matcher-name": "body",
        "host": "lifecycle.example",
    }


def _findings(*entries: dict) -> list[NormalizedFinding]:
    scanner = NucleiScanner()
    return scanner.normalize(scanner.parse(_jsonl(*entries)))


class NucleiIngestionLifecycleTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="nuclei-lifecycle@example.com", password="pass1234!"
        )
        self.website = Website.objects.create(
            owner=self.owner, domain="lifecycle.example"
        )
        self.organization = self.website.organization
        self.scan = Scan.objects.create(
            website=self.website,
            scan_type=Scan.ScanType.SECURITY,
            status=Scan.Status.RUNNING,
        )
        self.other_owner = User.objects.create_user(
            email="nuclei-lifecycle-other@example.com", password="pass1234!"
        )
        self.other_website = Website.objects.create(
            owner=self.other_owner, domain="lifecycle-other.example"
        )

    def _ingest(self, entries: list[dict], *, complete: bool = True):
        return ingest_scan_findings(
            scan=self.scan,
            scanner_name="nuclei",
            findings=_findings(*entries),
            complete=complete,
        )

    def _rows(self, **filters):
        return SecurityFinding.objects.filter(
            organization=self.organization, asset=self.website, **filters
        )

    def test_complete_report_creates_then_replay_updates_without_duplicates(self):
        first = self._ingest(
            [
                _entry("exposed-env-file", "Exposed .env File", "critical"),
                _entry("outdated-tls", "Outdated TLS", "medium"),
            ]
        )
        self.assertEqual((first.created, first.updated, first.resolved), (2, 0, 0))
        self.assertEqual(self._rows().count(), 2)

        second = self._ingest(
            [
                _entry("exposed-env-file", "Exposed .env File", "critical"),
                _entry("outdated-tls", "Outdated TLS", "medium"),
            ]
        )
        self.assertEqual((second.created, second.updated, second.resolved), (0, 2, 0))
        self.assertEqual(self._rows().count(), 2)

    def test_complete_report_can_resolve_a_missing_finding(self):
        self._ingest(
            [
                _entry("exposed-env-file", "Exposed .env File"),
                _entry("outdated-tls", "Outdated TLS", "medium"),
            ]
        )
        outcome = self._ingest(
            [_entry("exposed-env-file", "Exposed .env File")]
        )

        self.assertEqual(outcome.resolved, 1)
        resolved = self._rows().get(vulnerability_name="Outdated TLS")
        self.assertEqual(resolved.status, SecurityFinding.Status.RESOLVED)
        self.assertIsNotNone(resolved.resolved_at)
        self.assertEqual(
            self._rows().get(vulnerability_name="Exposed .env File").status,
            SecurityFinding.Status.OPEN,
        )

    def test_partial_report_never_resolves_absent_findings(self):
        self._ingest(
            [
                _entry("exposed-env-file", "Exposed .env File"),
                _entry("outdated-tls", "Outdated TLS", "medium"),
            ]
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
            findings=[timeout, *_findings(_entry("exposed-env-file", "Exposed .env File"))],
            complete=True,  # meta finding must force non-resolving ingest
        )

        self.assertEqual(outcome.resolved, 0)
        self.assertEqual(
            self._rows(status=SecurityFinding.Status.OPEN).count(), 2
        )

    def test_empty_complete_report_resolves_but_empty_partial_does_not(self):
        self._ingest([_entry("exposed-env-file", "Exposed .env File")])

        partial = ingest_scan_findings(
            scan=self.scan, scanner_name="nuclei", findings=[], complete=False
        )
        self.assertEqual(partial.resolved, 0)
        self.assertEqual(
            self._rows(status=SecurityFinding.Status.OPEN).count(), 1
        )

        complete = ingest_scan_findings(
            scan=self.scan, scanner_name="nuclei", findings=[], complete=True
        )
        self.assertEqual(complete.resolved, 1)
        self.assertEqual(
            self._rows(status=SecurityFinding.Status.OPEN).count(), 0
        )

    def test_malformed_jsonl_line_cannot_create_a_phantom_finding(self):
        raw = _jsonl(_entry("exposed-env-file", "Exposed .env File")) + "\n{not-json"
        scanner = NucleiScanner()
        parsed = scanner.parse(raw)
        self.assertEqual(len(parsed), 1)

        outcome = ingest_scan_findings(
            scan=self.scan,
            scanner_name="nuclei",
            findings=scanner.normalize(parsed),
            complete=True,
        )
        self.assertEqual(outcome.created, 1)
        self.assertEqual(self._rows().count(), 1)

    def test_other_tenant_and_asset_are_untouched(self):
        SecurityFinding.objects.create(
            organization=self.other_website.organization,
            asset=self.other_website,
            scanner_source="nuclei",
            vulnerability_name="Exposed .env File",
            severity=SecurityFinding.Severity.HIGH,
        )
        self._ingest([_entry("exposed-env-file", "Exposed .env File")])
        self._ingest([])

        other = SecurityFinding.objects.get(asset=self.other_website)
        self.assertEqual(other.status, SecurityFinding.Status.OPEN)
        self.assertEqual(
            self._rows(status=SecurityFinding.Status.OPEN).count(), 0
        )
