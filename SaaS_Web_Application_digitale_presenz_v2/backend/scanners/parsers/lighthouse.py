"""Lighthouse JSON report parser.

Lighthouse (https://github.com/GoogleChrome/lighthouse) emits a single JSON
document containing categories (performance, seo, accessibility,
best-practices) and ~150 audits.  This module turns that document into a small,
stable Python structure; converting it to ``NormalizedFinding`` objects is the
adapter's job (:mod:`scanners.implementations.lighthouse`).

The parser is deliberately defensive: Lighthouse output is produced by a
headless browser and may be prefixed by Chromium warnings, truncated by a
timeout, or contain ``null`` scores for audits that did not run.  It never
raises on malformed input — it returns ``None`` so the caller can record an
honest "parse_error" result instead of crashing the scan.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Sequence

#: Categories analysed by default (see SCANNER_LIGHTHOUSE_CATEGORIES).
DEFAULT_CATEGORIES: tuple[str, ...] = ("performance", "seo")

#: Human labels for the category scores exposed to AKA IA.
CATEGORY_LABELS: dict[str, str] = {
    "performance": "Performance",
    "seo": "SEO",
    "accessibility": "Accessibility",
    "best-practices": "Best Practices",
    "pwa": "PWA",
}

#: Core Web Vitals + payload audits that must always be reported, even when
#: they pass: they are the values the advisor reasons about over time.
CORE_METRICS: tuple[str, ...] = (
    "first-contentful-paint",
    "largest-contentful-paint",
    "total-blocking-time",
    "cumulative-layout-shift",
    "speed-index",
    "server-response-time",
    "total-byte-weight",
)

#: (good_max, poor_min, numeric_unit, expected_label)
METRIC_THRESHOLDS: dict[str, tuple[float, float, str, str]] = {
    "first-contentful-paint": (1_800.0, 3_000.0, "millisecond", "<= 1.8 s"),
    "largest-contentful-paint": (2_500.0, 4_000.0, "millisecond", "<= 2.5 s"),
    "total-blocking-time": (200.0, 600.0, "millisecond", "<= 200 ms"),
    "cumulative-layout-shift": (0.1, 0.25, "", "<= 0.1"),
    "speed-index": (3_400.0, 5_800.0, "millisecond", "<= 3.4 s"),
    "server-response-time": (800.0, 1_800.0, "millisecond", "<= 800 ms"),
    "total-byte-weight": (1_600_000.0, 3_000_000.0, "byte", "<= 1.6 MB"),
    "dom-size": (800.0, 1_400.0, "elements", "<= 800 elements"),
}

#: Audits that describe a measurable value but may not carry a score.
INFORMATIVE_MODES: frozenset[str] = frozenset(
    {"informative", "notapplicable", "manual", "error"}
)


@dataclass(frozen=True)
class LighthouseAudit:
    """One normalised Lighthouse audit."""

    audit_id: str
    category: str
    title: str
    description: str
    score: float | None
    score_display_mode: str
    display_value: str
    numeric_value: float | None
    numeric_unit: str
    weight: float

    @property
    def passed(self) -> bool:
        return self.score is not None and self.score >= 1.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.audit_id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "score": self.score,
            "scoreDisplayMode": self.score_display_mode,
            "displayValue": self.display_value,
            "numericValue": self.numeric_value,
            "numericUnit": self.numeric_unit,
            "weight": self.weight,
        }


@dataclass
class LighthouseReport:
    """Parsed Lighthouse report."""

    lighthouse_version: str = ""
    requested_url: str = ""
    final_url: str = ""
    fetch_time: str = ""
    user_agent: str = ""
    category_scores: dict[str, float | None] = field(default_factory=dict)
    audits: list[LighthouseAudit] = field(default_factory=list)
    runtime_error: dict[str, str] | None = None
    run_warnings: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def score_of(self, category: str) -> float | None:
        """Return the raw 0–1 score of *category* (``None`` if not measured)."""
        return self.category_scores.get(category)

    def percent_of(self, category: str) -> int | None:
        """Return the 0–100 score of *category* (``None`` if not measured)."""
        score = self.score_of(category)
        if score is None:
            return None
        return int(round(max(0.0, min(1.0, score)) * 100))

    def audits_for(self, category: str) -> list[LighthouseAudit]:
        return [a for a in self.audits if a.category == category]

    def metric(self, audit_id: str) -> LighthouseAudit | None:
        for audit in self.audits:
            if audit.audit_id == audit_id:
                return audit
        return None

    def core_metrics(self) -> dict[str, dict[str, Any]]:
        """Return the core metric audits in a compact, IA-friendly shape."""
        metrics: dict[str, dict[str, Any]] = {}
        for audit_id in CORE_METRICS:
            audit = self.metric(audit_id)
            if audit is None:
                continue
            metrics[audit_id] = {
                "value": audit.numeric_value,
                "unit": audit.numeric_unit,
                "display": audit.display_value,
                "score": audit.score,
            }
        return metrics

    def failed_audits(self) -> list[LighthouseAudit]:
        """Return failing/warning audits, highest impact first."""
        failing = [
            audit
            for audit in self.audits
            if audit.score is not None and audit.score < 1.0
        ]
        failing.sort(key=lambda audit: (audit.score or 1.0, -audit.weight))
        return failing

    @property
    def ok(self) -> bool:
        return self.runtime_error is None and bool(self.category_scores)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _load_json(output: str) -> dict[str, Any] | None:
    """Decode a Lighthouse JSON document, tolerating prefixed noise."""
    if not output or not output.strip():
        return None

    text = output.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Lighthouse/Chromium may print warnings before the JSON payload.
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None

    return data if isinstance(data, dict) else None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _category_audit_map(
    categories_raw: dict[str, Any],
    requested: Sequence[str],
) -> dict[str, tuple[str, float]]:
    """Map audit id → (category, weight), preferring requested categories."""
    mapping: dict[str, tuple[str, float]] = {}

    def _collect(category_id: str) -> None:
        category = categories_raw.get(category_id)
        if not isinstance(category, dict):
            return
        refs = category.get("auditRefs")
        if not isinstance(refs, list):
            return
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            audit_id = ref.get("id")
            if not isinstance(audit_id, str) or not audit_id:
                continue
            weight = _as_float(ref.get("weight")) or 0.0
            mapping.setdefault(audit_id, (category_id, weight))

    # Requested categories first so SEO-only audits keep their SEO label even
    # when the same audit also appears in accessibility.
    for category_id in requested:
        _collect(category_id)
    for category_id in categories_raw:
        _collect(category_id)

    return mapping


def parse_lighthouse_json(
    output: str,
    categories: Sequence[str] = DEFAULT_CATEGORIES,
) -> LighthouseReport | None:
    """Parse a Lighthouse JSON report.

    Parameters
    ----------
    output:
        Raw stdout of ``lighthouse --output=json --output-path=stdout``.
    categories:
        Categories to keep (default: performance + seo).

    Returns
    -------
    LighthouseReport | None
        ``None`` when the payload is not valid JSON.
    """
    raw = _load_json(output)
    if raw is None:
        return None

    requested = tuple(
        category for category in (categories or DEFAULT_CATEGORIES) if isinstance(category, str)
    ) or DEFAULT_CATEGORIES

    categories_raw = raw.get("categories")
    if not isinstance(categories_raw, dict):
        categories_raw = {}

    category_scores: dict[str, float | None] = {}
    for category_id in requested:
        category = categories_raw.get(category_id)
        if isinstance(category, dict):
            category_scores[category_id] = _as_float(category.get("score"))

    audit_map = _category_audit_map(categories_raw, requested)
    audits_raw = raw.get("audits")
    if not isinstance(audits_raw, dict):
        audits_raw = {}

    audits: list[LighthouseAudit] = []
    for audit_id, (category_id, weight) in audit_map.items():
        if category_id not in requested:
            continue

        item = audits_raw.get(audit_id)
        if not isinstance(item, dict):
            continue

        score = _as_float(item.get("score"))
        mode = _as_str(item.get("scoreDisplayMode")).lower()

        # Keep core metrics unconditionally; other audits only when they can
        # carry an actionable signal (a non-perfect score).
        is_core = audit_id in CORE_METRICS
        if not is_core:
            if mode in INFORMATIVE_MODES:
                continue
            if score is None or score >= 1.0:
                continue

        audits.append(
            LighthouseAudit(
                audit_id=audit_id,
                category=category_id,
                title=_as_str(item.get("title")) or audit_id,
                description=_as_str(item.get("description")),
                score=score,
                score_display_mode=mode or "unknown",
                display_value=_as_str(item.get("displayValue")),
                numeric_value=_as_float(item.get("numericValue")),
                numeric_unit=_as_str(item.get("numericUnit")),
                weight=weight,
            )
        )

    runtime_error_raw = raw.get("runtimeError")
    runtime_error: dict[str, str] | None = None
    if isinstance(runtime_error_raw, dict):
        runtime_error = {
            key: _as_str(runtime_error_raw.get(key))
            for key in ("code", "message")
            if runtime_error_raw.get(key)
        }

    warnings_raw = raw.get("runWarnings")
    run_warnings = (
        [str(item) for item in warnings_raw if isinstance(item, str)]
        if isinstance(warnings_raw, list)
        else []
    )

    return LighthouseReport(
        lighthouse_version=_as_str(raw.get("lighthouseVersion")),
        requested_url=_as_str(raw.get("requestedUrl")),
        final_url=_as_str(raw.get("finalUrl")),
        fetch_time=_as_str(raw.get("fetchTime")),
        user_agent=_as_str(raw.get("userAgent")),
        category_scores=category_scores,
        audits=audits,
        runtime_error=runtime_error,
        run_warnings=run_warnings,
    )
