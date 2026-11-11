"""Strict validation for the AI advisor JSON contract.

The model output is untrusted: it is parsed as JSON, validated by DRF
serializers (unknown keys are rejected), then every reference is resolved
against the original scan.  A recommendation must point to exactly one real
``Finding`` or ``CheckResult`` from that scan.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

from rest_framework import serializers

from advisory.models import AIRecommendation
from scans.models import CheckResult, Finding, Scan


class RecommendationValidationError(ValueError):
    """The model output is malformed or references another scan's data."""

    def __init__(
        self,
        message: str = "Invalid AI recommendation payload",
        *,
        errors: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.errors = errors


class RecommendationItemSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    summary = serializers.CharField(max_length=4000)
    action = serializers.CharField(max_length=4000)
    effort = serializers.ChoiceField(choices=AIRecommendation.Effort.choices)
    priority = serializers.ChoiceField(choices=AIRecommendation.Priority.choices)
    confidence = serializers.FloatField(min_value=0.0, max_value=1.0)
    check_code = serializers.CharField(
        max_length=128,
        required=False,
        allow_blank=True,
        default="",
    )
    finding_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise serializers.ValidationError("Each recommendation must be an object.")
        unknown = sorted(set(data) - set(self.fields))
        if unknown:
            raise serializers.ValidationError(
                {field: "Unknown field." for field in unknown}
            )
        return super().to_internal_value(data)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        confidence = attrs.get("confidence")
        if confidence is not None and not math.isfinite(confidence):
            raise serializers.ValidationError(
                {"confidence": "Confidence must be a finite number."}
            )

        check_code = (attrs.get("check_code") or "").strip()
        if attrs.get("finding_id") is None and not check_code:
            raise serializers.ValidationError(
                "Provide at least one of check_code or finding_id."
            )
        attrs["check_code"] = check_code
        return attrs


class RecommendationPayloadSerializer(serializers.Serializer):
    recommendations = RecommendationItemSerializer(many=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(self.initial_data, dict):
            raise serializers.ValidationError("The payload must be a JSON object.")
        unknown = sorted(set(self.initial_data) - set(self.fields))
        if unknown:
            raise serializers.ValidationError(
                {field: "Unknown field." for field in unknown}
            )

        items = attrs.get("recommendations") or []
        if not items:
            raise serializers.ValidationError(
                {"recommendations": "At least one recommendation is required."}
            )
        if len(items) > 12:
            raise serializers.ValidationError(
                {"recommendations": "At most 12 recommendations are allowed."}
            )
        return attrs


@dataclass(frozen=True)
class ResolvedRecommendation:
    title: str
    summary: str
    action: str
    effort: str
    priority: str
    confidence: float
    finding: Finding | None = None
    check_result: CheckResult | None = None


def parse_recommendation_content(content: str) -> dict[str, Any]:
    """Extract a JSON object, accepting an optional single markdown fence."""
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    if not text:
        raise RecommendationValidationError("The AI response is empty.")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RecommendationValidationError(
            "The AI response is not valid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise RecommendationValidationError("The AI response must be a JSON object.")
    return payload


def validate_recommendations(
    payload: dict[str, Any],
    scan: Scan,
) -> list[ResolvedRecommendation]:
    """Validate the payload and resolve every target inside *scan*."""
    serializer = RecommendationPayloadSerializer(data=payload)
    if not serializer.is_valid():
        raise RecommendationValidationError(
            "The AI recommendation payload does not match the schema.",
            errors=serializer.errors,
        )

    findings = list(
        Finding.objects.filter(scanner_run__scan=scan).select_related("scanner_run")
    )
    findings_by_id = {finding.id: finding for finding in findings}
    findings_by_code: dict[str, Finding] = {}
    for finding in findings:
        findings_by_code.setdefault(finding.check_code, finding)

    check_results = list(scan.check_results.all())
    check_results_by_code: dict[str, CheckResult] = {}
    for result in check_results:
        check_results_by_code.setdefault(result.category, result)
        check_results_by_code.setdefault(f"{result.category}.overall", result)

    resolved: list[ResolvedRecommendation] = []
    for item in serializer.validated_data["recommendations"]:
        finding_id = item.get("finding_id")
        check_code = (item.get("check_code") or "").strip()
        target_finding: Finding | None = None
        target_check: CheckResult | None = None

        if finding_id is not None:
            target_finding = findings_by_id.get(finding_id)
            if target_finding is None:
                raise RecommendationValidationError(
                    f"finding_id {finding_id} does not belong to this scan."
                )
            if check_code and target_finding.check_code != check_code:
                raise RecommendationValidationError(
                    "finding_id and check_code do not refer to the same finding."
                )
        elif check_code:
            target_finding = findings_by_code.get(check_code)
            if target_finding is None:
                target_check = check_results_by_code.get(check_code)
            if target_finding is None and target_check is None:
                raise RecommendationValidationError(
                    f"check_code {check_code!r} does not belong to this scan."
                )
        else:
            raise RecommendationValidationError(
                "Provide at least one of check_code or finding_id."
            )

        resolved.append(
            ResolvedRecommendation(
                title=item["title"],
                summary=item["summary"],
                action=item["action"],
                effort=item["effort"],
                priority=item["priority"],
                confidence=float(item["confidence"]),
                finding=target_finding,
                check_result=target_check,
            )
        )

    return resolved


def parse_and_validate(
    content: str,
    scan: Scan,
) -> list[ResolvedRecommendation]:
    return validate_recommendations(parse_recommendation_content(content), scan)
