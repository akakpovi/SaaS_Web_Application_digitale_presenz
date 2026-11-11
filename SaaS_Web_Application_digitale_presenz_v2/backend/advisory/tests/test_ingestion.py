"""Parsing, upsert and provenance tests for scanner report ingestion.

The pipeline must never lose these properties:

* an uploaded report is recognised as ZAP or Nuclei, and an unrecognised file
  is rejected instead of being read as "zero findings" (which would resolve
  everything open on the asset);
* replaying the same report updates in place — no duplicate rows, no lost
  detection timestamp, a previously resolved finding reopens;
* a finding absent from a report is resolved, but only within the same
  organization *and* asset *and* scanner source;
* the import endpoint is scoped by organization and restricted to roles that
  may rewrite the tenant's findings.
"""

from __future__ import annotations

import json
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from advisory.models import SecurityFinding
from advisory.parsers import (
    MAX_NAME_CHARS,
    ReportParseError,
    detect_source,
    normalise_severity,
    parse_report,
)
from advisory.services.ingestion import AssetTenantMismatch, ingest_report
from organizations.models import Membership, Organization
from websites.models import Website

# --------------------------------------------------------------------------
# Sample payloads (shapes taken from real ZAP / Nuclei output)
# --------------------------------------------------------------------------

ZAP_REPORT = {
    "site": [
        {
            "alerts": [
                {
                    "pluginid": "40012",
                    "name": "Cross Site Scripting (Reflected)",
                    "riskdesc": "High (Medium)",
                    "riskcode": "3",
                    "confidence": "Medium",
                    "desc": "The parameter is echoed without encoding.",
                    "solution": "Encode the parameter before writing it.",
                    "cweid": "79",
                    "instances": [
                        {
                            "uri": "https://shop.example/search?q=abc",
                            "method": "GET",
                            "param": "q",
                            "evidence": "<script>alert(1)</script>",
                        }
                    ],
                },
                {
                    "pluginid": "10038",
                    "name": "Content Security Policy Header Not Set",
                    "riskdesc": "Informational (High)",
                    "desc": "No CSP header on responses.",
                    "solution": "Send a Content-Security-Policy header.",
                },
            ]
        }
    ]
}

NUCLEI_LINES = [
    {
        "template-id": "exposed-env-file",
        "info": {
            "name": "Exposed .env File",
            "severity": "critical",
            "description": "The environment file is publicly readable.",
            "tags": ["exposure", "config"],
        },
        "matched-at": "https://shop.example/.env",
        "matcher-name": "status-200",
        "extracted-results": ["APP_KEY=redacted"],
        "host": "shop.example",
        "curl-command": "curl -s https://shop.example/.env",
    },
    {
        "template-id": "tls-version",
        "info": {
            "name": "Deprecated TLS Version",
            "severity": "high",
            "description": "TLS 1.0 is still accepted.",
        },
        "matched-at": "https://shop.example:443",
    },
]


def nuclei_body(lines=None) -> str:
    return "\n".join(json.dumps(line) for line in (lines or NUCLEI_LINES))


def zap_body(report=None) -> str:
    return json.dumps(report or ZAP_REPORT)


def make_tenant(email: str, domain: str) -> tuple[User, Organization, Website]:
    user = User.objects.create_user(email=email, password="pass1234!")
    website = Website.objects.create(owner=user, domain=domain)
    return user, website.organization, website


class ParserTests(SimpleTestCase):
    def test_zap_report_is_mapped_to_finding_fields(self):
        report = parse_report(zap_body())

        self.assertEqual(report.source, "zap")
        self.assertEqual(len(report.findings), 2)

        xss = next(f for f in report.findings if "Cross Site" in f.vulnerability_name)
        self.assertEqual(xss.severity, "high")
        self.assertIn("echoed without encoding", xss.description)
        self.assertIn("Solution: Encode the parameter", xss.description)
        self.assertIn("https://shop.example/search?q=abc", xss.proof_or_payload)
        self.assertIn("evidence: <script>alert(1)</script>", xss.proof_or_payload)
        self.assertIn("parameter: q", xss.proof_or_payload)

    def test_zap_informational_risk_maps_to_info(self):
        report = parse_report(zap_body())
        csp = next(
            f for f in report.findings if "Content Security" in f.vulnerability_name
        )
        self.assertEqual(csp.severity, "info")

    def test_zap_supports_the_core_alerts_payload(self):
        body = json.dumps(
            {
                "alerts": [
                    {
                        "pluginid": "10021",
                        "alert": "Missing Anti-clickjacking Header",
                        "name": "Missing Anti-clickjacking Header",
                        "riskdesc": "Medium (Medium)",
                        "desc": "No X-Frame-Options header.",
                    }
                ]
            }
        )
        report = parse_report(body)
        self.assertEqual(report.source, "zap")
        self.assertEqual(report.findings[0].severity, "medium")

    def test_nuclei_jsonl_is_mapped_to_finding_fields(self):
        report = parse_report(nuclei_body())

        self.assertEqual(report.source, "nuclei")
        self.assertEqual(len(report.findings), 2)

        env = next(
            f for f in report.findings if f.vulnerability_name == "Exposed .env File"
        )
        self.assertEqual(env.severity, "critical")
        self.assertIn("publicly readable", env.description)
        self.assertIn("template: exposed-env-file", env.proof_or_payload)
        self.assertIn("matched at: https://shop.example/.env", env.proof_or_payload)
        self.assertIn("matcher: status-200", env.proof_or_payload)
        self.assertIn("extracted: APP_KEY=redacted", env.proof_or_payload)
        self.assertIn("curl: curl -s https://shop.example/.env", env.proof_or_payload)

    def test_nuclei_json_array_is_accepted(self):
        report = parse_report(json.dumps(NUCLEI_LINES))

        self.assertEqual(report.source, "nuclei")
        self.assertEqual(len(report.findings), 2)

    def test_detect_source_recognises_both_formats(self):
        self.assertEqual(detect_source(zap_body()), "zap")
        self.assertEqual(detect_source(nuclei_body()), "nuclei")
        self.assertEqual(detect_source('{"site": []}'), "zap")
        self.assertIsNone(detect_source('{"unrelated": true}'))
        self.assertIsNone(detect_source("not json at all"))

    def test_empty_report_resolves_nothing_but_is_recognised(self):
        report = parse_report('{"site": []}')
        self.assertEqual(report.source, "zap")
        self.assertEqual(report.findings, ())

    def test_unknown_document_is_rejected(self):
        with self.assertRaises(ReportParseError) as caught:
            parse_report('{"something": "else"}')
        self.assertEqual(caught.exception.code, "unknown_report_format")

        with self.assertRaises(ReportParseError) as caught:
            parse_report("plain text, not JSON")
        self.assertEqual(caught.exception.code, "unknown_report_format")

    def test_empty_upload_is_rejected(self):
        with self.assertRaises(ReportParseError) as caught:
            parse_report("   ")
        self.assertEqual(caught.exception.code, "empty_report")

    def test_explicit_source_must_match_the_payload(self):
        with self.assertRaises(ReportParseError) as caught:
            parse_report(nuclei_body(), source="zap")
        self.assertEqual(caught.exception.code, "report_format_mismatch")

        with self.assertRaises(ReportParseError) as caught:
            parse_report(zap_body(), source="nessus")
        self.assertEqual(caught.exception.code, "unsupported_source")

    def test_repeated_alerts_are_collapsed_into_one_finding(self):
        report = {
            "site": [
                {
                    "alerts": [
                        {
                            "pluginid": "40012",
                            "name": "Cross Site Scripting",
                            "riskdesc": "High (Medium)",
                            "desc": "Reflected parameter.",
                            "instances": [{"uri": "https://shop.example/a?q=1"}],
                        },
                        {
                            "pluginid": "40012",
                            "name": "Cross Site Scripting",
                            "riskdesc": "Low (Medium)",
                            "desc": "Reflected parameter.",
                            "instances": [{"uri": "https://shop.example/b?q=2"}],
                        },
                    ]
                }
            ]
        }
        parsed = parse_report(json.dumps(report))

        self.assertEqual(len(parsed.findings), 1)
        self.assertEqual(parsed.skipped, 1)
        self.assertEqual(parsed.findings[0].severity, "high")
        self.assertIn("https://shop.example/a?q=1", parsed.findings[0].proof_or_payload)
        self.assertIn("https://shop.example/b?q=2", parsed.findings[0].proof_or_payload)

    def test_names_are_bounded_and_never_empty(self):
        report = {
            "alerts": [
                {
                    "pluginid": "1",
                    "riskcode": "2",
                    "desc": "x" * 10,
                    "name": "N" * 400,
                }
            ]
        }
        parsed = parse_report(json.dumps(report))
        self.assertEqual(len(parsed.findings[0].vulnerability_name), MAX_NAME_CHARS)

    def test_severity_aliases_are_normalised(self):
        for raw, expected in (
            ("Informational", "info"),
            ("unknown", "info"),
            ("CRITICAL", "critical"),
            ("weird-label", "info"),
            (None, "info"),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(normalise_severity(raw), expected)


class IngestionServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner, self.organization, self.asset = make_tenant(
            "ingest-owner@example.com", "ingest-owner.example"
        )
        self.other_user, self.other_org, self.other_asset = make_tenant(
            "ingest-other@example.com", "ingest-other.example"
        )
        # Second asset of the *same* tenant, to prove resolution is per asset.
        self.second_asset = Website.objects.create(
            owner=self.owner, domain="ingest-owner-second.example"
        )
        self.assertEqual(self.second_asset.organization_id, self.organization.pk)

    def ingest(self, body: str, *, asset=None, organization=None, now=None):
        report = parse_report(body)
        return ingest_report(
            organization or self.organization,
            asset or self.asset,
            report,
            now=now,
        )

    def findings(self, **filters):
        return SecurityFinding.objects.filter(
            organization=self.organization, asset=self.asset, **filters
        )

    def test_first_import_creates_every_finding(self):
        outcome = self.ingest(nuclei_body())

        self.assertEqual(outcome.source, "nuclei")
        self.assertEqual(outcome.received, 2)
        self.assertEqual(outcome.created, 2)
        self.assertEqual(outcome.updated, 0)
        self.assertEqual(outcome.resolved, 0)
        self.assertEqual(self.findings().count(), 2)

        finding = self.findings(scanner_source="nuclei").get(
            vulnerability_name="Exposed .env File"
        )
        self.assertEqual(finding.organization, self.organization)
        self.assertEqual(finding.asset, self.asset)
        self.assertEqual(finding.status, SecurityFinding.Status.OPEN)
        self.assertIsNone(finding.resolved_at)

    def test_replaying_a_report_updates_in_place(self):
        start = timezone.now() - timedelta(days=3)
        self.ingest(zap_body(), now=start)

        replay_at = timezone.now()
        outcome = self.ingest(zap_body(), now=replay_at)

        self.assertEqual(outcome.created, 0)
        self.assertEqual(outcome.updated, 2)
        self.assertEqual(outcome.resolved, 0)
        self.assertEqual(self.findings().count(), 2)

        xss = self.findings().get(vulnerability_name="Cross Site Scripting (Reflected)")
        self.assertEqual(xss.detected_at, replay_at)
        self.assertGreater(xss.detected_at, start)
        self.assertEqual(xss.status, SecurityFinding.Status.OPEN)
        self.assertIsNone(xss.resolved_at)

    def test_resolved_finding_reopens_when_seen_again(self):
        self.ingest(nuclei_body())
        finding = self.findings().get(vulnerability_name="Exposed .env File")
        finding.resolve()
        self.assertEqual(self.findings(status="resolved").count(), 1)

        outcome = self.ingest(nuclei_body())

        finding.refresh_from_db()
        self.assertEqual(outcome.updated, 2)
        self.assertEqual(outcome.created, 0)
        self.assertEqual(finding.status, SecurityFinding.Status.OPEN)
        self.assertIsNone(finding.resolved_at)

    def test_findings_missing_from_the_new_report_are_resolved(self):
        self.ingest(nuclei_body())

        reduced = nuclei_body([NUCLEI_LINES[0]])
        resolved_at = timezone.now()
        outcome = self.ingest(reduced, now=resolved_at)

        self.assertEqual(outcome.resolved, 1)
        gone = self.findings().get(vulnerability_name="Deprecated TLS Version")
        self.assertEqual(gone.status, SecurityFinding.Status.RESOLVED)
        self.assertEqual(gone.resolved_at, resolved_at)
        still_open = self.findings().get(vulnerability_name="Exposed .env File")
        self.assertEqual(still_open.status, SecurityFinding.Status.OPEN)

    def test_resolution_is_scoped_to_asset_and_source(self):
        self.ingest(nuclei_body())

        same_asset_other_source = SecurityFinding.objects.create(
            organization=self.organization,
            asset=self.asset,
            scanner_source="zap",
            vulnerability_name="Deprecated TLS Version",
            severity=SecurityFinding.Severity.HIGH,
        )
        other_asset = SecurityFinding.objects.create(
            organization=self.organization,
            asset=self.second_asset,
            scanner_source="nuclei",
            vulnerability_name="Deprecated TLS Version",
            severity=SecurityFinding.Severity.HIGH,
        )
        other_tenant = SecurityFinding.objects.create(
            organization=self.other_org,
            asset=self.other_asset,
            scanner_source="nuclei",
            vulnerability_name="Deprecated TLS Version",
            severity=SecurityFinding.Severity.HIGH,
        )

        self.ingest(nuclei_body([NUCLEI_LINES[0]]))

        for untouched in (same_asset_other_source, other_asset, other_tenant):
            untouched.refresh_from_db()
            self.assertEqual(untouched.status, SecurityFinding.Status.OPEN)
            self.assertIsNone(untouched.resolved_at)

    def test_empty_report_resolves_every_open_finding_of_that_asset_and_source(self):
        self.ingest(nuclei_body())
        self.ingest(zap_body())

        outcome = self.ingest('{"site": []}')

        self.assertEqual(outcome.source, "zap")
        self.assertEqual(outcome.received, 0)
        self.assertEqual(outcome.resolved, 2)
        self.assertEqual(self.findings(status="resolved").count(), 2)
        self.assertEqual(
            self.findings(scanner_source="nuclei", status="open").count(), 2
        )

    def test_empty_report_does_not_touch_another_tenant(self):
        SecurityFinding.objects.create(
            organization=self.other_org,
            asset=self.other_asset,
            scanner_source="zap",
            vulnerability_name="Cross Site Scripting (Reflected)",
            severity=SecurityFinding.Severity.HIGH,
        )

        self.ingest('{"site": []}')

        self.assertEqual(
            SecurityFinding.objects.filter(
                organization=self.other_org, status="open"
            ).count(),
            1,
        )

    def test_asset_from_another_tenant_is_refused_by_the_service(self):
        report = parse_report(nuclei_body())
        with self.assertRaises(AssetTenantMismatch):
            ingest_report(self.other_org, self.asset, report)

    def test_database_forbids_duplicate_findings_for_one_asset_and_source(self):
        self.ingest(nuclei_body())

        with self.assertRaises(IntegrityError), transaction.atomic():
            SecurityFinding.objects.create(
                organization=self.organization,
                asset=self.asset,
                scanner_source="nuclei",
                vulnerability_name="Exposed .env File",
                severity=SecurityFinding.Severity.CRITICAL,
            )

    def test_ingestion_never_touches_other_tenants_rows(self):
        self.ingest(nuclei_body())

        self.assertEqual(
            SecurityFinding.objects.filter(organization=self.other_org).count(), 0
        )


class ImportEndpointTests(APITestCase):
    def setUp(self) -> None:
        self.owner, self.organization, self.asset = make_tenant(
            "import-owner@example.com", "import-owner.example"
        )
        self.admin = User.objects.create_user(
            email="import-admin@example.com", password="pass1234!"
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.admin,
            role=Membership.Role.ADMIN,
        )
        self.analyst = User.objects.create_user(
            email="import-analyst@example.com", password="pass1234!"
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.analyst,
            role=Membership.Role.ANALYST,
        )
        self.viewer = User.objects.create_user(
            email="import-viewer@example.com", password="pass1234!"
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.viewer,
            role=Membership.Role.VIEWER,
        )
        self.outsider, self.other_org, self.other_asset = make_tenant(
            "import-outsider@example.com", "import-outsider.example"
        )
        self.url = reverse(
            "asset-scan-report-import",
            kwargs={
                "organization_id": self.organization.id,
                "asset_id": self.asset.pk,
            },
        )

    def upload(self, body: str, *, url: str | None = None, name="report.json", **extra):
        payload = {"file": SimpleUploadedFile(name, body.encode(), "application/json")}
        payload.update(extra)
        return self.client.post(url or self.url, payload, format="multipart")

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def test_owner_imports_a_nuclei_report(self):
        self.as_user(self.owner)
        response = self.upload(nuclei_body())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "nuclei")
        self.assertEqual(response.data["asset_id"], self.asset.pk)
        self.assertEqual(response.data["received"], 2)
        self.assertEqual(response.data["created"], 2)
        self.assertEqual(response.data["updated"], 0)
        self.assertEqual(response.data["resolved"], 0)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(
            SecurityFinding.objects.filter(
                organization=self.organization, asset=self.asset
            ).count(),
            2,
        )

    def test_admin_can_import(self):
        self.as_user(self.admin)
        response = self.upload(zap_body())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "zap")
        self.assertEqual(response.data["created"], 2)

    def test_response_never_contains_evidence(self):
        self.as_user(self.owner)
        response = self.upload(zap_body())

        body = json.dumps(response.data)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertNotIn("evidence", body)

    def test_replaying_the_same_upload_updates_instead_of_duplicating(self):
        self.as_user(self.owner)
        first = self.upload(nuclei_body())
        second = self.upload(nuclei_body())

        self.assertEqual(first.data["created"], 2)
        self.assertEqual(second.data["created"], 0)
        self.assertEqual(second.data["updated"], 2)
        self.assertEqual(second.data["resolved"], 0)

    def test_import_resolves_findings_missing_from_the_new_report(self):
        self.as_user(self.owner)
        self.upload(nuclei_body())
        response = self.upload(nuclei_body([NUCLEI_LINES[0]]))

        self.assertEqual(response.data["resolved"], 1)
        self.assertTrue(
            SecurityFinding.objects.filter(
                organization=self.organization,
                asset=self.asset,
                vulnerability_name="Deprecated TLS Version",
                status=SecurityFinding.Status.RESOLVED,
            ).exists()
        )

    def test_analyst_and_viewer_cannot_import(self):
        for user in (self.analyst, self.viewer):
            with self.subTest(role=user.email):
                self.as_user(user)
                response = self.upload(nuclei_body())
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.assertIn("role", response.data)
        self.assertEqual(SecurityFinding.objects.count(), 0)

    def test_outsider_gets_404_not_403(self):
        self.as_user(self.outsider)
        response = self.upload(nuclei_body())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(SecurityFinding.objects.count(), 0)

    def test_anonymous_is_rejected(self):
        response = self.upload(nuclei_body())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_asset_of_another_tenant_is_not_reachable(self):
        self.as_user(self.owner)
        foreign_url = reverse(
            "asset-scan-report-import",
            kwargs={
                "organization_id": self.organization.id,
                "asset_id": self.other_asset.pk,
            },
        )
        response = self.upload(nuclei_body(), url=foreign_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(SecurityFinding.objects.count(), 0)

    def test_missing_file_is_a_clean_400(self):
        self.as_user(self.owner)
        response = self.client.post(self.url, {}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "file_required")

    def test_unrecognised_report_is_rejected_without_resolving_anything(self):
        self.as_user(self.owner)
        self.upload(nuclei_body())

        response = self.upload('{"unrelated": "payload"}')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "unknown_report_format")
        self.assertEqual(
            SecurityFinding.objects.filter(status=SecurityFinding.Status.OPEN).count(),
            2,
        )

    def test_explicit_source_mismatch_is_rejected(self):
        self.as_user(self.owner)
        response = self.upload(nuclei_body(), source="zap")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "report_format_mismatch")

    def test_explicit_source_is_honoured_for_ambiguous_files(self):
        self.as_user(self.owner)
        body = json.dumps(NUCLEI_LINES)
        response = self.upload(body, source="nuclei")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source"], "nuclei")

    def test_non_utf8_upload_is_rejected(self):
        self.as_user(self.owner)
        upload = SimpleUploadedFile(
            "report.json", b"\xff\xfe\x00bad", "application/json"
        )
        response = self.client.post(self.url, {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "invalid_encoding")

    def test_import_is_tenant_scoped(self):
        other_url = reverse(
            "asset-scan-report-import",
            kwargs={
                "organization_id": self.other_org.id,
                "asset_id": self.other_asset.pk,
            },
        )
        self.as_user(self.outsider)
        response = self.upload(nuclei_body(), url=other_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            SecurityFinding.objects.filter(organization=self.other_org).count(), 2
        )
        self.assertEqual(
            SecurityFinding.objects.filter(organization=self.organization).count(), 0
        )
