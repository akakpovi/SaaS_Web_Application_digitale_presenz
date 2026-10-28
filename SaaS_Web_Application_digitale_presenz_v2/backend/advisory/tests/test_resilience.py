from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock
from typing import Any

from django.db import IntegrityError
from django.test import TestCase, override_settings

from accounts.models import User
from advisory.models import AIRecommendation, AIRecommendationRun
from advisory.services.advisor import (
    MAX_CHECK_RESULTS,
    MAX_CRITICAL_FINDINGS,
    MAX_FINDINGS,
    _claim_run,
    build_messages,
    build_scan_snapshot,
    generate_recommendations_for_scan,
)
from advisory.services.aka_client import (
    AkaCompletion,
    AkaServerError,
)
from scans.models import CheckResult, Finding, Scan, ScannerRun
from websites.models import Website


def _payload() -> str:
    return json.dumps(
        {
            "recommendations": [
                {
                    "title": "Renew the TLS certificate",
                    "summary": "The certificate expires soon.",
                    "action": "Renew it before the expiry date.",
                    "effort": "low",
                    "priority": "high",
                    "confidence": 0.92,
                    "check_code": "ssl.overall",
                }
            ]
        }
    )


def _completion() -> AkaCompletion:
    return AkaCompletion(
        id="chatcmpl-1",
        model="model-a",
        content=_payload(),
        finish_reason="stop",
        latency_ms=10,
    )


class FakeClient:
    def __init__(self, outcomes: dict[str, Any]) -> None:
        self.outcomes = outcomes
        self.config = SimpleNamespace(models=tuple(outcomes))
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages, *, model=None, **kwargs):
        self.calls.append({"messages": messages, "model": model})
        outcome = self.outcomes[model]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class AdvisorResilienceTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="resilience-advisor@example.com",
            password="pass1234!",
        )
        self.website = Website.objects.create(
            owner=self.user,
            domain="resilience-advisor.example",
        )
        self.scan = Scan.objects.create(
            website=self.website,
            status=Scan.Status.COMPLETED,
            health_score=50,
        )
        self.scanner_run = ScannerRun.objects.create(
            scan=self.scan,
            scanner="ssl",
        )
        self.check_result = CheckResult.objects.create(
            scan=self.scan,
            category=CheckResult.Category.SSL,
            status="critical",
            score=0,
            summary="Certificate expires soon.",
            recommendation="Renew the certificate.",
        )

    def _make_many_findings(self, *, large_text: bool = False) -> None:
        Finding.objects.bulk_create(
            [
                Finding(
                    scanner_run=self.scanner_run,
                    category="ssl",
                    check_code=f"ssl.critical_{index}",
                    title=f"Critical issue {index}",
                    description="x" * (4_000 if large_text else 20),
                    severity=Finding.Severity.CRITICAL,
                    status=Finding.Status.FAIL,
                    evidence={"note": "y" * (4_000 if large_text else 20)},
                )
                for index in range(20)
            ]
        )
        Finding.objects.bulk_create(
            [
                Finding(
                    scanner_run=self.scanner_run,
                    category="dns",
                    check_code=f"dns.high_{index}",
                    title=f"High issue {index}",
                    severity=Finding.Severity.HIGH,
                    status=Finding.Status.WARNING,
                )
                for index in range(5)
            ]
        )
        CheckResult.objects.bulk_create(
            [
                CheckResult(
                    scan=self.scan,
                    category=f"extra_{index}",
                    status="warning",
                    score=0,
                    summary="Extra check",
                    recommendation="Fix this check.",
                )
                for index in range(11)
            ]
        )

    def test_findings_and_checks_are_ranked_and_capped(self) -> None:
        self._make_many_findings()

        snapshot = build_scan_snapshot(self.scan)
        limits = snapshot["evidence_limits"]

        self.assertEqual(limits["critical_findings_total"], 20)
        self.assertEqual(limits["critical_findings_included"], MAX_CRITICAL_FINDINGS)
        self.assertLessEqual(len(snapshot["findings"]), MAX_FINDINGS)
        self.assertEqual(limits["check_results_total"], 12)
        self.assertEqual(len(snapshot["check_results"]), MAX_CHECK_RESULTS)
        self.assertEqual(limits["check_results_truncated"], 2)
        self.assertTrue(limits["findings_truncated"] >= 5)

    @override_settings(AKA_AI_MAX_PROMPT_CHARS=12_000)
    def test_prompt_size_is_strictly_bounded(self) -> None:
        self._make_many_findings(large_text=True)

        snapshot = build_scan_snapshot(self.scan)
        messages = build_messages(snapshot)
        evidence = messages[1]["content"].split("\n", 1)[1]

        self.assertLessEqual(len(evidence), 12_000)
        self.assertLessEqual(snapshot["evidence_limits"]["prompt_chars"], 12_000)

    def test_large_text_is_truncated(self) -> None:
        Finding.objects.create(
            scanner_run=self.scanner_run,
            category="ssl",
            check_code="ssl.large",
            title="Large finding",
            description="z" * 100_000,
            severity=Finding.Severity.HIGH,
            status=Finding.Status.FAIL,
        )

        snapshot = build_scan_snapshot(self.scan)
        finding = next(item for item in snapshot["findings"] if item["check_code"] == "ssl.large")

        self.assertLessEqual(len(finding["description"]), 3_100)
        self.assertIn("[truncated]", finding["description"])

    def test_failed_run_can_be_reclaimed_only_when_explicitly_requested(self) -> None:
        failed_client = FakeClient(
            {"model-a": AkaServerError("unavailable", status_code=503)}
        )
        first = generate_recommendations_for_scan(
            self.scan.pk,
            client=failed_client,
        )
        self.assertTrue(first.used_fallback)
        self.assertEqual(first.run.attempts, 1)
        # A provider outage is transient: the Celery task must retry it with
        # backoff instead of leaving the scan without any AI analysis.
        self.assertEqual(first.error_code, "AkaServerError")
        self.assertTrue(first.should_retry)

        success_client = FakeClient({"model-a": _completion()})
        not_retried = generate_recommendations_for_scan(
            self.scan.pk,
            client=success_client,
        )
        self.assertTrue(not_retried.used_fallback)
        self.assertEqual(success_client.calls, [])

        retried = generate_recommendations_for_scan(
            self.scan.pk,
            client=success_client,
            retry_failed=True,
        )

        self.assertFalse(retried.used_fallback)
        self.assertEqual(retried.run.id, first.run.id)
        self.assertEqual(retried.run.attempts, 2)
        self.assertEqual(len(success_client.calls), 1)
        self.assertEqual(AIRecommendation.objects.filter(run=retried.run).count(), 1)

    def test_integrity_error_race_is_recovered(self) -> None:
        input_hash = "c" * 64
        run = AIRecommendationRun.objects.create(
            scan=self.scan,
            input_hash=input_hash,
            status=AIRecommendationRun.Status.FAILED,
            attempts=1,
        )

        with mock.patch.object(
            AIRecommendationRun.objects,
            "create",
            side_effect=IntegrityError("duplicate"),
        ):
            claimed_run, claimed = _claim_run(
                scan=self.scan,
                input_hash=input_hash,
                retry_failed=True,
            )

        self.assertTrue(claimed)
        self.assertEqual(claimed_run.pk, run.pk)
        self.assertEqual(claimed_run.attempts, 2)

    def test_running_run_is_not_reclaimed_by_a_second_worker(self) -> None:
        input_hash = "d" * 64
        AIRecommendationRun.objects.create(
            scan=self.scan,
            input_hash=input_hash,
            status=AIRecommendationRun.Status.RUNNING,
            attempts=1,
        )

        with mock.patch.object(
            AIRecommendationRun.objects,
            "create",
            side_effect=IntegrityError("duplicate"),
        ):
            claimed_run, claimed = _claim_run(
                scan=self.scan,
                input_hash=input_hash,
                retry_failed=True,
            )

        self.assertFalse(claimed)
        self.assertEqual(claimed_run.status, AIRecommendationRun.Status.RUNNING)
        self.assertEqual(claimed_run.attempts, 1)
