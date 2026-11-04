"""Steps builder for scan progress tracking.

Defines the ordered list of scanner steps for each scan type.
This list is stored in Scan.steps and updated in real-time as the
orchestrator progresses through each scanner.
"""

from __future__ import annotations

from typing import Any


class StepStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"


# Canonical step definitions per scan type.
# Order matters — steps are presented in this order in the UI.
_HEALTH_STEPS: list[dict[str, Any]] = [
    {"key": "website", "label": "Website Availability", "scanner": "website", "weight": 15},
    {"key": "ssl", "label": "SSL / TLS Certificate", "scanner": "ssl", "weight": 15},
    {"key": "dns", "label": "DNS Configuration", "scanner": "dns", "weight": 15},
    {"key": "email_security", "label": "Email Security", "scanner": "email_security", "weight": 15},
    {"key": "security_headers", "label": "Security Headers", "scanner": "security_headers", "weight": 15},
    {"key": "performance", "label": "Performance", "scanner": "performance", "weight": 15},
    {
        "key": "lighthouse",
        "label": "Performance & SEO (Lighthouse)",
        "scanner": "lighthouse",
        "weight": 10,
        # The legacy performance scanner already runs in this scan.  Lighthouse
        # enriches the result but is not a required security control, so its
        # unavailability must not make an otherwise complete scan "partial".
        "optional": True,
    },
    {"key": "uptime", "label": "Uptime Check", "scanner": "uptime", "weight": 10},
]

_SECURITY_STEPS: list[dict[str, Any]] = [
    {"key": "nmap", "label": "Port Scan (Nmap)", "scanner": "nmap", "weight": 15},
    {"key": "nikto", "label": "Web Vulnerabilities (Nikto)", "scanner": "nikto", "weight": 20},
    {"key": "nuclei", "label": "Template Scan (Nuclei)", "scanner": "nuclei", "weight": 20},
    {"key": "whatweb", "label": "Technology Detection (WhatWeb)", "scanner": "whatweb", "weight": 10},
    {"key": "testssl", "label": "TLS Deep Analysis (testssl.sh)", "scanner": "testssl", "weight": 15},
    {"key": "dnsrecon", "label": "DNS Recon (dnsrecon)", "scanner": "dnsrecon", "weight": 10},
    {"key": "gobuster", "label": "Directory Enumeration (Gobuster)", "scanner": "gobuster", "weight": 5},
    {"key": "zap", "label": "Active Scan (OWASP ZAP)", "scanner": "zap", "weight": 5},
]

_FULL_STEPS: list[dict[str, Any]] = _HEALTH_STEPS + _SECURITY_STEPS

#: Progressive journey stage 1: one fast, bounded TLS pass.  The budget for
#: the whole stage is 150 s (``SCAN_JOURNEY_STAGE1_TIME_BUDGET_SECONDS``);
#: testssl keeps its 120 s per-step timeout, so the adapter can still close
#: its report before the orchestrator reaches the stage deadline.
_JOURNEY_STAGE1_STEPS: list[dict[str, Any]] = [
    {
        "key": "testssl",
        "label": "TLS Deep Analysis (testssl.sh)",
        "scanner": "testssl",
        "weight": 100,
    },
]

#: Progressive journey stage 2 (scenario C).  Nikto is deliberately absent:
#: the optimised Nuclei profile plus the original Presence templates replace
#: it for journeys only.  Classic scans keep ``_SECURITY_STEPS`` unchanged.
_JOURNEY_STAGE2_STEPS: list[dict[str, Any]] = [
    {
        "key": "nuclei",
        "label": "Optimised Template Scan (Nuclei)",
        "scanner": "nuclei",
        "weight": 25,
        "profile": "scenario_c",
        "timeout_setting": "SCAN_JOURNEY_STAGE2_NUCLEI_TIMEOUT",
    },
    {
        "key": "gobuster",
        "label": "Directory Enumeration (Gobuster)",
        "scanner": "gobuster",
        "weight": 10,
        "timeout_setting": "SCAN_JOURNEY_STAGE2_GOBUSTER_TIMEOUT",
    },
]


def build_initial_steps(
    scan_type: str,
    *,
    journey_stage: int | None = None,
) -> list[dict[str, Any]]:
    """Return the initial steps list for a given scan type.

    ``journey_stage=1`` selects the bounded TLS stage and ``journey_stage=2``
    the scenario-C pipeline, regardless of the scan type.  Every other value,
    including ``None``, keeps the historical behaviour exactly: classic scans
    never see the journey profiles.
    """
    if journey_stage == 1:
        template = _JOURNEY_STAGE1_STEPS
    elif journey_stage == 2:
        template = _JOURNEY_STAGE2_STEPS
    elif scan_type == "security":
        template = _SECURITY_STEPS
    elif scan_type == "full":
        template = _FULL_STEPS
    else:
        template = _HEALTH_STEPS  # Default: health

    steps: list[dict[str, Any]] = []
    for step in template:
        item = {
            "key": step["key"],
            "label": step["label"],
            "scanner": step["scanner"],
            "weight": step["weight"],
            # Every configured step is required by default.  A policy gate
            # (e.g. the advanced-security feature flag) explicitly marks a
            # step optional before skipping it, so an intentional skip does
            # not downgrade an otherwise complete scan.
            "required": not bool(step.get("optional", False)),
            "status": StepStatus.PENDING,
            "progress": 0,
            "duration_ms": None,
            "error": None,
        }
        if step.get("profile"):
            item["profile"] = step["profile"]
        if step.get("timeout_setting"):
            item["timeout_setting"] = step["timeout_setting"]
        steps.append(item)
    return steps


def get_steps_for_scan(scan: Any) -> list[dict[str, Any]]:
    """Select the pipeline for *scan* without changing classic scans.

    A journey child is fully defined by its ``journey_stage``; a classic scan
    (``journey_stage=None``) keeps its historical, scan-type-based pipeline.
    """
    return build_initial_steps(
        getattr(scan, "scan_type", "health"),
        journey_stage=getattr(scan, "journey_stage", None),
    )


def compute_overall_progress(steps: list[dict[str, Any]]) -> int:
    """Compute overall scan progress (0–100) from the steps list.

    Uses weighted averaging based on step ``weight``.
    """
    if not steps:
        return 0

    total_weight = sum(s.get("weight", 1) for s in steps)
    if total_weight == 0:
        return 0

    weighted_sum = 0
    for step in steps:
        status = step.get("status", StepStatus.PENDING)
        step_weight = step.get("weight", 1)
        step_progress = step.get("progress", 0)

        if status in (StepStatus.COMPLETED, StepStatus.PARTIAL,
                      StepStatus.FAILED, StepStatus.TIMEOUT,
                      StepStatus.UNAVAILABLE, StepStatus.SKIPPED):
            # Completed steps contribute their full weight.
            weighted_sum += step_weight * 100
        elif status == StepStatus.RUNNING:
            weighted_sum += step_weight * step_progress
        # PENDING contributes 0.

    return int(weighted_sum / total_weight)
