"""Non-regression tests for the SSL scoring separation.

The ``ssl`` category is owned by the legacy certificate scanner: it is the
only scanner allowed to create the weighted ``ssl`` CheckResult.  ``testssl``
is a findings-only enrichment covering a much broader TLS surface, so it must
never create or overwrite that CheckResult — otherwise classic and journey
scans report different SSL scores for the same site (see commit 2aeb507).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase

from accounts.models import User
from scans.models import CheckResult, Finding, Scan, ScannerRun
from scans.services.orchestrator import ScanOrchestrator
from scanners.base import (
    FindingStatus,
    NormalizedFinding,
    ScanOutcome,
    ScanResult,
    ScannerType,
    Severity,
)
from scanners.security.target_validator import TargetInfo
from websites.models import Website


def _user() -> User:
    return User.objects.create_user(
        "ssl-separation@example.com", "CorrectHorseBattery1!"
    )


def _website(user: User) -> Website:
    return Website.objects.create(owner=user, domain="ssl-separation.example")


def _target() -> TargetInfo:
    return TargetInfo(
        hostname="ssl-separation.example",
        url="https://ssl-separation.example",
        safe_ips=["93.184.216.34"],
        scheme="https",
    )


def _step(key: str, scanner: str) -> dict:
    return {
        "key": key,
        "label": key.title(),
        "scanner": scanner,
        "weight": 100,
        "status": "pending",
        "progress": 0,
        "duration_ms": None,
        "error": None,
    }


def _scanner(
    name: str,
    *,
    score: int | None,
    status: str,
    details: dict,
    findings: list[NormalizedFinding],
) -> MagicMock:
    """Mock adapter returning one ScanOutcome, like the delegation tests."""
    scanner = MagicMock()
    scanner.name = name
    scanner.scanner_type = ScannerType.CLI
    scanner.check_result_category = None
    scanner.timeout = 120
    scanner.is_available.return_value = True
    scanner.execute.return_value = ScanOutcome(
        result=ScanResult(
            score=score,
            status=status,
            message=f"{name} summary",
            details=details,
        ),
        findings=findings,
    )
    return scanner


def _finding(code: str, severity: str, title: str) -> NormalizedFinding:
    return NormalizedFinding(
        check_code=code,
        category="ssl",
        severity=severity,
        status=FindingStatus.FAIL,
        title=title,
    )


class SSLScoringSeparationTests(TestCase):
    """testssl findings-only; the legacy ssl scanner owns the CheckResult."""

    def setUp(self) -> None:
        self.user = _user()
        self.website = _website(self.user)

    def _run(self, scanners: list[MagicMock], steps: list[dict]) -> Scan:
        scan = Scan.objects.create(
            website=self.website, status=Scan.Status.QUEUED
        )
        with patch("scanners.registry.ScannerRegistry") as mock_registry, patch(
            "scans.services.steps_builder.build_initial_steps",
            return_value=steps,
        ), patch(
            "scanners.security.target_validator.validate_target",
            return_value=_target(),
        ), patch(
            "scans.services.scoring.recalculate_scan_health"
        ):
            mock_registry.get.side_effect = scanners
            ScanOrchestrator(scan.id).run()
        return scan

    def test_legacy_ssl_creates_the_scored_check_result(self) -> None:
        scanner = _scanner(
            "ssl",
            score=16,
            status="healthy",
            details={"scanner": "ssl", "days_until_expiry": 44},
            findings=[
                _finding(
                    "ssl.certificate_expiry",
                    Severity.INFO,
                    "SSL certificate expires in 44 days",
                )
            ],
        )

        scan = self._run([scanner], [_step("ssl", "ssl")])

        result = CheckResult.objects.get(
            scan=scan, category=CheckResult.Category.SSL
        )
        self.assertEqual(result.score, 16)
        self.assertEqual(result.technical_details["scanner"], "ssl")
        self.assertEqual(
            ScannerRun.objects.get(scan=scan).status,
            ScannerRun.Status.COMPLETED,
        )

    def test_testssl_creates_findings_without_ssl_check_result(self) -> None:
        findings = [
            _finding("testssl.TLS1_0", Severity.MEDIUM, "TLS 1.0 offered"),
            _finding("testssl.TLS1_1", Severity.MEDIUM, "TLS 1.1 offered"),
            _finding("testssl.BREACH", Severity.LOW, "BREACH vulnerable"),
            _finding("testssl.cert_valid", Severity.INFO, "Certificate valid"),
        ]
        scanner = _scanner(
            "testssl",
            score=5,
            status="neutral",
            details={"scan_complete": True, "total_checks": 4},
            findings=findings,
        )

        scan = self._run([scanner], [_step("testssl", "testssl")])

        self.assertFalse(
            CheckResult.objects.filter(
                scan=scan, category=CheckResult.Category.SSL
            ).exists(),
            "testssl must not create a CheckResult in category 'ssl'",
        )

        run = ScannerRun.objects.get(scan=scan)
        self.assertEqual(run.scanner, "testssl")
        self.assertEqual(Finding.objects.filter(scanner_run=run).count(), 4)

    def test_journey_stage_order_keeps_the_legacy_score(self) -> None:
        ssl_scanner = _scanner(
            "ssl",
            score=16,
            status="healthy",
            details={"scanner": "ssl", "days_until_expiry": 44},
            findings=[
                _finding(
                    "ssl.certificate_expiry",
                    Severity.INFO,
                    "SSL certificate expires in 44 days",
                )
            ],
        )
        testssl_scanner = _scanner(
            "testssl",
            score=5,
            status="neutral",
            details={"scan_complete": True, "total_checks": 3},
            findings=[
                _finding("testssl.TLS1_0", Severity.MEDIUM, "TLS 1.0 offered"),
                _finding("testssl.TLS1_1", Severity.MEDIUM, "TLS 1.1 offered"),
                _finding("testssl.BREACH", Severity.LOW, "BREACH vulnerable"),
            ],
        )

        scan = self._run(
            [ssl_scanner, testssl_scanner],
            [_step("ssl", "ssl"), _step("testssl", "testssl")],
        )

        results = CheckResult.objects.filter(
            scan=scan, category=CheckResult.Category.SSL
        )
        self.assertEqual(
            results.count(),
            1,
            "the ssl category must be written exactly once",
        )
        result = results.get()
        self.assertEqual(result.score, 16)
        self.assertEqual(result.technical_details["scanner"], "ssl")

        self.assertEqual(
            Finding.objects.filter(scanner_run__scan=scan).count(), 4
        )
        self.assertEqual(
            set(
                ScannerRun.objects.filter(scan=scan).values_list(
                    "status", flat=True
                )
            ),
            {ScannerRun.Status.COMPLETED},
        )
