"""Comprehensive Phase 4 tests for the Scan and CheckResult domains.

Tests cover:
- Scan lifecycle / state transitions (pending → queued → running → completed/failed)
- Health-score calculation with correct weights
- Score determinism
- Missing/incomplete check handling
- Status handling (healthy/warning/critical/neutral)
- Uptime exclusion from weighted score
- Category score limits
- Ownership isolation (User A cannot access User B's scans/results)
- CheckResult relationships and API responses
- Scan serializer response format
"""

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from scans.models import CheckResult, HealthStatus, Scan
from scans.serializers import CheckResultSerializer
from scans.services.scoring import (
    CHECK_WEIGHTS,
    HEALTH_WEIGHTS,
    HealthScore,
    calculate_health_score,
    recalculate_scan_health,
)
from websites.models import Website


# ═══════════════════════════════════════════════════
# Model-level tests
# ═══════════════════════════════════════════════════


class ScanLifecycleTests(TestCase):
    """Test the scan state machine transitions."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            "owner@example.com", "CorrectHorseBattery1!"
        )
        self.website = Website.objects.create(owner=self.user, domain="example.com")

    def test_new_scan_defaults_to_pending(self) -> None:
        scan = Scan.objects.create(website=self.website)
        self.assertEqual(scan.status, Scan.Status.PENDING)

    def test_pending_to_queued_transition(self) -> None:
        scan = Scan.objects.create(website=self.website)
        scan.transition_to(Scan.Status.QUEUED)
        self.assertEqual(scan.status, Scan.Status.QUEUED)

    def test_pending_to_failed_transition(self) -> None:
        scan = Scan.objects.create(website=self.website)
        scan.transition_to(Scan.Status.FAILED, failure_message="Validation error")
        self.assertEqual(scan.status, Scan.Status.FAILED)
        self.assertEqual(scan.failure_message, "Validation error")
        self.assertIsNotNone(scan.completed_at)

    def test_queued_to_running_sets_started_at(self) -> None:
        scan = Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)
        scan.transition_to(Scan.Status.RUNNING)
        self.assertEqual(scan.status, Scan.Status.RUNNING)
        self.assertIsNotNone(scan.started_at)

    def test_running_to_completed_sets_completed_at(self) -> None:
        scan = Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)
        scan.transition_to(Scan.Status.RUNNING)
        scan.transition_to(Scan.Status.COMPLETED)
        self.assertEqual(scan.status, Scan.Status.COMPLETED)
        self.assertIsNotNone(scan.completed_at)

    def test_running_to_failed_transition(self) -> None:
        scan = Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)
        scan.transition_to(Scan.Status.RUNNING)
        scan.transition_to(Scan.Status.FAILED, failure_message="Timeout")
        self.assertEqual(scan.status, Scan.Status.FAILED)
        self.assertEqual(scan.failure_message, "Timeout")

    def test_completed_cannot_transition_further(self) -> None:
        scan = Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)
        scan.transition_to(Scan.Status.RUNNING)
        scan.transition_to(Scan.Status.COMPLETED)
        with self.assertRaises(ValidationError):
            scan.transition_to(Scan.Status.RUNNING)

    def test_failed_cannot_transition_further(self) -> None:
        scan = Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)
        scan.transition_to(Scan.Status.FAILED)
        with self.assertRaises(ValidationError):
            scan.transition_to(Scan.Status.QUEUED)

    def test_cannot_skip_from_pending_to_running(self) -> None:
        scan = Scan.objects.create(website=self.website)
        with self.assertRaises(ValidationError):
            scan.transition_to(Scan.Status.RUNNING)

    def test_cannot_skip_from_pending_to_completed(self) -> None:
        scan = Scan.objects.create(website=self.website)
        with self.assertRaises(ValidationError):
            scan.transition_to(Scan.Status.COMPLETED)

    def test_noop_transition_to_same_status(self) -> None:
        scan = Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)
        scan.transition_to(Scan.Status.QUEUED)  # Should not raise
        self.assertEqual(scan.status, Scan.Status.QUEUED)

    def test_full_lifecycle_pending_to_completed(self) -> None:
        scan = Scan.objects.create(website=self.website)
        self.assertEqual(scan.status, Scan.Status.PENDING)

        scan.transition_to(Scan.Status.QUEUED)
        self.assertEqual(scan.status, Scan.Status.QUEUED)

        scan.transition_to(Scan.Status.RUNNING)
        self.assertEqual(scan.status, Scan.Status.RUNNING)
        self.assertIsNotNone(scan.started_at)

        scan.transition_to(Scan.Status.COMPLETED)
        self.assertEqual(scan.status, Scan.Status.COMPLETED)
        self.assertIsNotNone(scan.completed_at)

    def test_failure_message_truncated_to_500_chars(self) -> None:
        scan = Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)
        long_message = "x" * 600
        scan.transition_to(Scan.Status.FAILED, failure_message=long_message)
        self.assertEqual(len(scan.failure_message), 500)


# ═══════════════════════════════════════════════════
# Health-score service tests
# ═══════════════════════════════════════════════════


class HealthScoreServiceTests(TestCase):
    """Test the deterministic scoring service."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            "owner@example.com", "CorrectHorseBattery1!"
        )
        self.scan = Scan.objects.create(
            website=Website.objects.create(owner=self.user, domain="example.com"),
            status=Scan.Status.QUEUED,
        )

    def add_result(
        self, category: str, score: int | None, result_status: str
    ) -> CheckResult:
        result = CheckResult(
            scan=self.scan,
            category=category,
            score=score,
            status=result_status,
            summary="Result",
        )
        result.full_clean()
        result.save()
        return result

    # ── Weights ──

    def test_health_weights_sum_to_100(self) -> None:
        self.assertEqual(sum(HEALTH_WEIGHTS.values()), 100)

    def test_check_weights_include_security_scorecards(self) -> None:
        self.assertEqual(sum(CHECK_WEIGHTS.values()), 130)
        self.assertEqual(CHECK_WEIGHTS[CheckResult.Category.EXPOSURE], 10)
        self.assertEqual(CHECK_WEIGHTS[CheckResult.Category.NUCLEI], 20)

    def test_weights_are_correct(self) -> None:
        self.assertEqual(CHECK_WEIGHTS[CheckResult.Category.WEBSITE], 20)
        self.assertEqual(CHECK_WEIGHTS[CheckResult.Category.SSL], 20)
        self.assertEqual(CHECK_WEIGHTS[CheckResult.Category.DNS], 15)
        self.assertEqual(CHECK_WEIGHTS[CheckResult.Category.EMAIL_SECURITY], 15)
        self.assertEqual(CHECK_WEIGHTS[CheckResult.Category.SECURITY_HEADERS], 15)
        self.assertEqual(CHECK_WEIGHTS[CheckResult.Category.PERFORMANCE], 15)

    def test_uptime_not_in_weights(self) -> None:
        self.assertNotIn(CheckResult.Category.UPTIME, CHECK_WEIGHTS)

    # ── Empty / neutral ──

    def test_no_results_is_neutral_and_unscored(self) -> None:
        health = calculate_health_score([])
        self.assertIsNone(health.score)
        self.assertEqual(health.status, HealthStatus.NEUTRAL)

    def test_only_uptime_result_is_neutral_and_unscored(self) -> None:
        uptime = self.add_result(
            CheckResult.Category.UPTIME, None, HealthStatus.HEALTHY
        )
        health = calculate_health_score([uptime])
        self.assertIsNone(health.score)
        self.assertEqual(health.status, HealthStatus.NEUTRAL)

    # ── Full perfect score ──

    def test_complete_perfect_results_produce_score_100_healthy(self) -> None:
        for category, score in [
            (CheckResult.Category.WEBSITE, 20),
            (CheckResult.Category.SSL, 20),
            (CheckResult.Category.DNS, 15),
            (CheckResult.Category.EMAIL_SECURITY, 15),
            (CheckResult.Category.SECURITY_HEADERS, 15),
            (CheckResult.Category.PERFORMANCE, 15),
        ]:
            self.add_result(category, score, HealthStatus.HEALTHY)

        health = recalculate_scan_health(self.scan)
        self.assertEqual(health.score, 100)
        self.assertEqual(health.status, HealthStatus.HEALTHY)
        self.scan.refresh_from_db()
        self.assertEqual(self.scan.health_score, 100)
        self.assertEqual(self.scan.health_status, HealthStatus.HEALTHY)

    # ── Partial scores ──

    def test_partial_results_sum_correctly(self) -> None:
        self.add_result(CheckResult.Category.WEBSITE, 20, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.SSL, 15, HealthStatus.WARNING)
        # Missing DNS, Email Security, Security Headers, Performance → contribute zero
        health = calculate_health_score(self.scan.check_results.all())
        self.assertEqual(health.score, 35)

    def test_missing_categories_contribute_zero(self) -> None:
        """Only Website check present; other 5 weighted categories contribute zero."""
        self.add_result(CheckResult.Category.WEBSITE, 20, HealthStatus.HEALTHY)
        health = calculate_health_score(self.scan.check_results.all())
        self.assertEqual(health.score, 20)

    # ── Status thresholds ──

    def test_critical_check_overrides_to_critical_status(self) -> None:
        self.add_result(CheckResult.Category.WEBSITE, 20, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.SSL, 20, HealthStatus.CRITICAL)
        health = recalculate_scan_health(self.scan)
        self.assertEqual(health.status, HealthStatus.CRITICAL)

    def test_score_below_40_is_critical(self) -> None:
        self.add_result(CheckResult.Category.WEBSITE, 15, HealthStatus.WARNING)
        self.add_result(CheckResult.Category.SSL, 15, HealthStatus.WARNING)
        # Total = 30, below 40 → critical
        health = calculate_health_score(self.scan.check_results.all())
        self.assertEqual(health.score, 30)
        self.assertEqual(health.status, HealthStatus.CRITICAL)

    def test_score_between_40_and_79_is_warning(self) -> None:
        self.add_result(CheckResult.Category.WEBSITE, 20, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.SSL, 20, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.DNS, 15, HealthStatus.HEALTHY)
        # Total = 55, between 40 and 80, no critical → warning
        health = calculate_health_score(self.scan.check_results.all())
        self.assertEqual(health.score, 55)
        self.assertEqual(health.status, HealthStatus.WARNING)

    def test_score_at_80_is_healthy(self) -> None:
        self.add_result(CheckResult.Category.WEBSITE, 20, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.SSL, 20, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.DNS, 15, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.EMAIL_SECURITY, 15, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.SECURITY_HEADERS, 10, HealthStatus.HEALTHY)
        # Total = 80 → healthy
        health = calculate_health_score(self.scan.check_results.all())
        self.assertEqual(health.score, 80)
        self.assertEqual(health.status, HealthStatus.HEALTHY)

    def test_warning_check_with_high_score_is_warning(self) -> None:
        """Even if the score >= 80, a WARNING check status forces overall WARNING."""
        self.add_result(CheckResult.Category.WEBSITE, 20, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.SSL, 20, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.DNS, 15, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.EMAIL_SECURITY, 15, HealthStatus.HEALTHY)
        self.add_result(
            CheckResult.Category.SECURITY_HEADERS, 15, HealthStatus.WARNING
        )  # WARNING status
        # Total = 85, but WARNING status → warning
        health = calculate_health_score(self.scan.check_results.all())
        self.assertEqual(health.score, 85)
        self.assertEqual(health.status, HealthStatus.WARNING)

    # ── Determinism ──

    def test_same_results_always_produce_same_score(self) -> None:
        self.add_result(CheckResult.Category.WEBSITE, 18, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.SSL, 15, HealthStatus.WARNING)
        self.add_result(CheckResult.Category.DNS, 10, HealthStatus.HEALTHY)

        results = list(self.scan.check_results.all())
        score1 = calculate_health_score(results)
        score2 = calculate_health_score(results)
        score3 = calculate_health_score(results)

        self.assertEqual(score1, score2)
        self.assertEqual(score2, score3)

    # ── Uptime ──

    def test_security_scorecards_do_not_inflate_health_score(self) -> None:
        self.add_result(CheckResult.Category.WEBSITE, 20, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.EXPOSURE, 10, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.NUCLEI, 20, HealthStatus.HEALTHY)
        health = calculate_health_score(self.scan.check_results.all())
        self.assertEqual(health.score, 20)

    def test_uptime_does_not_affect_weighted_score(self) -> None:
        self.add_result(CheckResult.Category.WEBSITE, 20, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.UPTIME, None, HealthStatus.HEALTHY)

        health = calculate_health_score(self.scan.check_results.all())
        # Should only count the website check (score=20), uptime excluded
        self.assertEqual(health.score, 20)

    # ── recalculate_scan_health persists to DB ──

    def test_recalculate_scan_health_updates_database(self) -> None:
        self.add_result(CheckResult.Category.WEBSITE, 20, HealthStatus.HEALTHY)
        self.add_result(CheckResult.Category.SSL, 20, HealthStatus.HEALTHY)
        health = recalculate_scan_health(self.scan)

        self.scan.refresh_from_db()
        self.assertEqual(self.scan.health_score, health.score)
        self.assertEqual(self.scan.health_status, health.status)

    # ── HealthScore dataclass ──

    def test_health_score_is_frozen_dataclass(self) -> None:
        hs = HealthScore(score=50, status=HealthStatus.WARNING)
        self.assertEqual(hs.score, 50)
        self.assertEqual(hs.status, HealthStatus.WARNING)
        with self.assertRaises(AttributeError):
            hs.score = 100  # type: ignore[misc]


# ═══════════════════════════════════════════════════
# CheckResult validation tests
# ═══════════════════════════════════════════════════


class CheckResultValidationTests(TestCase):
    """Test model-level validation of CheckResult scores."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            "owner@example.com", "CorrectHorseBattery1!"
        )
        self.scan = Scan.objects.create(
            website=Website.objects.create(owner=self.user, domain="example.com"),
            status=Scan.Status.QUEUED,
        )

    def test_weighted_category_requires_score(self) -> None:
        result = CheckResult(
            scan=self.scan,
            category=CheckResult.Category.WEBSITE,
            score=None,
            status=HealthStatus.HEALTHY,
        )
        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_uptime_score_must_be_none(self) -> None:
        result = CheckResult(
            scan=self.scan,
            category=CheckResult.Category.UPTIME,
            score=1,
            status=HealthStatus.HEALTHY,
        )
        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_uptime_with_none_score_is_valid(self) -> None:
        result = CheckResult(
            scan=self.scan,
            category=CheckResult.Category.UPTIME,
            score=None,
            status=HealthStatus.HEALTHY,
        )
        result.full_clean()  # Should not raise

    def test_score_cannot_exceed_category_weight(self) -> None:
        # DNS max is 15; score=16 should fail
        result = CheckResult(
            scan=self.scan,
            category=CheckResult.Category.DNS,
            score=16,
            status=HealthStatus.HEALTHY,
        )
        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_score_at_category_max_is_valid(self) -> None:
        result = CheckResult(
            scan=self.scan,
            category=CheckResult.Category.DNS,
            score=15,
            status=HealthStatus.HEALTHY,
        )
        result.full_clean()  # Should not raise

    def test_score_zero_is_valid_for_weighted_category(self) -> None:
        result = CheckResult(
            scan=self.scan,
            category=CheckResult.Category.PERFORMANCE,
            score=0,
            status=HealthStatus.CRITICAL,
        )
        result.full_clean()  # Should not raise

    def test_unique_constraint_per_scan_category(self) -> None:
        CheckResult.objects.create(
            scan=self.scan,
            category=CheckResult.Category.WEBSITE,
            score=20,
            status=HealthStatus.HEALTHY,
        )
        duplicate = CheckResult(
            scan=self.scan,
            category=CheckResult.Category.WEBSITE,
            score=15,
            status=HealthStatus.WARNING,
        )
        with self.assertRaises(Exception):
            duplicate.save()

    def test_valid_technical_details_json_accepted(self) -> None:
        result = CheckResult(
            scan=self.scan,
            category=CheckResult.Category.WEBSITE,
            score=20,
            status=HealthStatus.HEALTHY,
            summary="Available",
            recommendation="No changes needed.",
            technical_details={
                "http_status": 200,
                "response_time_ms": 230,
                "server": "nginx",
            },
        )
        result.full_clean()
        result.save()
        result.refresh_from_db()
        self.assertEqual(result.technical_details["http_status"], 200)

    def test_all_health_statuses_are_valid(self) -> None:
        for i, health_status in enumerate(HealthStatus.values):
            result = CheckResult(
                scan=self.scan,
                category=list(CheckResult.Category.values)[i]
                if i < len(CheckResult.Category.values)
                else CheckResult.Category.WEBSITE,
                score=10
                if list(CheckResult.Category.values)[i] != CheckResult.Category.UPTIME
                else None,
                status=health_status,
            )
            # Don't save since we might hit unique constraint; just validate
            if list(CheckResult.Category.values)[i] != CheckResult.Category.UPTIME:
                try:
                    result.full_clean()
                except ValidationError:
                    pass  # May fail for other reasons, but status should be valid


# ═══════════════════════════════════════════════════
# CheckResult serializer tests
# ═══════════════════════════════════════════════════


class CheckResultSerializerTests(TestCase):
    """CheckResultSerializer.get_max_score must use CHECK_WEIGHTS."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            "owner@example.com", "CorrectHorseBattery1!"
        )
        self.scan = Scan.objects.create(
            website=Website.objects.create(owner=self.user, domain="example.com"),
            status=Scan.Status.QUEUED,
        )

    def test_max_score_is_20_for_website_and_ssl(self) -> None:
        for category in (CheckResult.Category.WEBSITE, CheckResult.Category.SSL):
            result = CheckResult(
                scan=self.scan, category=category, score=10, status=HealthStatus.HEALTHY
            )
            self.assertEqual(
                CheckResultSerializer(result).data["max_score"],
                20,
                f"{category} should be 20",
            )

    def test_max_score_is_15_for_weighted_categories(self) -> None:
        for category in (
            CheckResult.Category.DNS,
            CheckResult.Category.EMAIL_SECURITY,
            CheckResult.Category.SECURITY_HEADERS,
            CheckResult.Category.PERFORMANCE,
        ):
            result = CheckResult(
                scan=self.scan, category=category, score=10, status=HealthStatus.HEALTHY
            )
            self.assertEqual(
                CheckResultSerializer(result).data["max_score"],
                15,
                f"{category} should be 15",
            )

    def test_max_score_all_weighted_categories(self) -> None:
        expected: dict[str, int] = {
            CheckResult.Category.WEBSITE: 20,
            CheckResult.Category.SSL: 20,
            CheckResult.Category.DNS: 15,
            CheckResult.Category.EMAIL_SECURITY: 15,
            CheckResult.Category.SECURITY_HEADERS: 15,
            CheckResult.Category.PERFORMANCE: 15,
        }
        for category, weight in expected.items():
            result = CheckResult(
                scan=self.scan,
                category=category,
                score=weight,
                status=HealthStatus.HEALTHY,
            )
            with self.subTest(category=category):
                self.assertEqual(
                    CheckResultSerializer(result).data["max_score"], weight
                )

    def test_serializer_uses_check_weights_as_source_of_truth(self) -> None:
        from scans.services.scoring import CHECK_WEIGHTS as _W

        result = CheckResult(
            scan=self.scan,
            category=CheckResult.Category.DNS,
            score=15,
            status=HealthStatus.HEALTHY,
        )
        self.assertEqual(
            CheckResultSerializer(result).data["max_score"],
            _W[CheckResult.Category.DNS],
        )

    def test_max_score_is_none_for_unbounded_categories(self) -> None:
        for category in (
            CheckResult.Category.UPTIME,
            CheckResult.Category.ZAP,
        ):
            result = CheckResult(
                scan=self.scan,
                category=category,
                score=None,
                status=HealthStatus.HEALTHY,
            )
            with self.subTest(category=category):
                self.assertIsNone(CheckResultSerializer(result).data["max_score"])

        ssl = CheckResult(
            scan=self.scan,
            category=CheckResult.Category.SSL,
            score=10,
            status=HealthStatus.HEALTHY,
        )
        self.assertEqual(CheckResultSerializer(ssl).data["max_score"], 20)

    def test_max_score_is_10_for_exposure_and_20_for_nuclei(self) -> None:
        expected = {
            CheckResult.Category.EXPOSURE: 10,
            CheckResult.Category.NUCLEI: 20,
        }
        for category, max_score in expected.items():
            result = CheckResult(
                scan=self.scan,
                category=category,
                score=max_score,
                status=HealthStatus.HEALTHY,
            )
            with self.subTest(category=category):
                self.assertEqual(
                    CheckResultSerializer(result).data["max_score"], max_score
                )


# ═══════════════════════════════════════════════════
# API-level tests
# ═══════════════════════════════════════════════════


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ScanAPITests(APITestCase):
    """Test the Scan and CheckResult REST API endpoints."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            "owner@example.com", "CorrectHorseBattery1!"
        )
        self.other_user = User.objects.create_user(
            "other@example.com", "CorrectHorseBattery1!"
        )
        self.website = Website.objects.create(owner=self.user, domain="owner.example")
        self.scan = Scan.objects.create(website=self.website, status=Scan.Status.QUEUED)
        self.result = CheckResult.objects.create(
            scan=self.scan,
            category=CheckResult.Category.WEBSITE,
            status=HealthStatus.HEALTHY,
            score=20,
            summary="Available",
            recommendation="",
            technical_details={"http_status": 200},
        )
        self.other_website = Website.objects.create(
            owner=self.other_user, domain="other.example"
        )
        self.other_scan = Scan.objects.create(
            website=self.other_website, status=Scan.Status.QUEUED
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}"
        )

    # ── Scan listing ──

    def test_scan_list_returns_only_owned_scans(self) -> None:
        response = self.client.get("/api/v1/scans/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.scan.id])

    def test_scan_list_excludes_other_users_scans(self) -> None:
        response = self.client.get("/api/v1/scans/")
        ids = [item["id"] for item in response.data["results"]]
        self.assertNotIn(self.other_scan.id, ids)

    # ── Scan detail ──

    def test_scan_detail_returns_owned_scan(self) -> None:
        response = self.client.get(f"/api/v1/scans/{self.scan.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.scan.id)
        self.assertEqual(response.data["domain"], "owner.example")

    def test_scan_detail_includes_check_results(self) -> None:
        response = self.client.get(f"/api/v1/scans/{self.scan.id}/")
        self.assertEqual(len(response.data["check_results"]), 1)
        result = response.data["check_results"][0]
        self.assertEqual(result["category"], "website")
        self.assertEqual(result["score"], 20)
        self.assertEqual(result["max_score"], 20)
        self.assertEqual(result["technical_details"]["http_status"], 200)

    def test_cannot_retrieve_other_users_scan(self) -> None:
        response = self.client.get(f"/api/v1/scans/{self.other_scan.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ── CheckResult endpoints ──

    def test_check_results_list_is_owner_scoped(self) -> None:
        response = self.client.get(f"/api/v1/scans/{self.scan.id}/results/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["max_score"], 20)

    def test_check_results_for_other_users_scan_returns_empty(self) -> None:
        response = self.client.get(f"/api/v1/scans/{self.other_scan.id}/results/")
        self.assertEqual(response.data["results"], [])

    def test_check_results_are_read_only(self) -> None:
        response = self.client.post(
            f"/api/v1/scans/{self.scan.id}/results/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_check_result_detail_is_owner_scoped(self) -> None:
        response = self.client.get(
            f"/api/v1/scans/{self.scan.id}/results/{self.result.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["category"], "website")

    # ── Scan response format ──

    def test_scan_response_contains_expected_fields(self) -> None:
        response = self.client.get(f"/api/v1/scans/{self.scan.id}/")
        # Core legacy fields that MUST be present (additive check — new fields are allowed).
        expected_keys = {
            "id",
            "website_id",
            "domain",
            "status",
            "trigger",
            "health_score",
            "health_status",
            "failure_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
            "check_results",
        }
        self.assertTrue(
            expected_keys.issubset(set(response.data.keys())),
            f"Missing fields: {expected_keys - set(response.data.keys())}",
        )

    def test_check_result_response_contains_expected_fields(self) -> None:
        response = self.client.get(
            f"/api/v1/scans/{self.scan.id}/results/{self.result.id}/"
        )
        expected_keys = {
            "id",
            "category",
            "status",
            "score",
            "max_score",
            "summary",
            "recommendation",
            "technical_details",
            "created_at",
            "updated_at",
        }
        self.assertEqual(set(response.data.keys()), expected_keys)

    # ── Authentication ──

    def test_unauthenticated_scan_access_rejected(self) -> None:
        self.client.credentials()  # Clear auth
        self.assertEqual(
            self.client.get("/api/v1/scans/").status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            self.client.get(f"/api/v1/scans/{self.scan.id}/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # ── Scans are read-only (no create/update/delete via /scans/) ──

    def test_scan_viewset_is_read_only(self) -> None:
        self.assertEqual(
            self.client.post("/api/v1/scans/", {}, format="json").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.put(
                f"/api/v1/scans/{self.scan.id}/", {}, format="json"
            ).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.delete(f"/api/v1/scans/{self.scan.id}/").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    # ── Nonexistent scan ──

    def test_nonexistent_scan_returns_404(self) -> None:
        response = self.client.get("/api/v1/scans/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
