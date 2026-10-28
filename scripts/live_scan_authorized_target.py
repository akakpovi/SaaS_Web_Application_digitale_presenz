#!/usr/bin/env python3
"""Run one live, authorized scan against appchat.elomaiapp.com.

The target is deliberately hard-coded: this script exists to prove the
sandboxed ZAP/Nuclei path on the one domain the operator authorized, and it
refuses any other host.

It queues a ``full`` scan (health + security) through the public API and waits
for completion, then prints the ZAP/Nuclei CheckResults and Finding counts.

Usage::

    python3 scripts/live_scan_authorized_target.py \
        --base-url https://localhost/api/v1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import requests

AUTHORIZED_DOMAIN = "appchat.elomaiapp.com"
OWNER = "phasef.smoke.owner@presence.local"
PASSWORD = os.environ.get("SMOKE_PASSWORD", "PhaseF-Live-2026!")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://localhost/api/v1")
    parser.add_argument("--scan-timeout", type=int, default=600)
    parser.add_argument("--scan-type", default="full", choices=["full", "security"])
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    session = requests.Session()
    session.verify = False
    requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]

    login = session.post(
        f"{base}/auth/login/", json={"email": OWNER, "password": PASSWORD}
    )
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['access']}"}

    organizations = session.get(f"{base}/organizations/", headers=headers)
    organizations.raise_for_status()
    orgs = organizations.json()
    orgs = orgs["results"] if isinstance(orgs, dict) else orgs
    org = next((item for item in orgs if item["role"] == "owner"), None)
    if org is None:
        raise SystemExit("owner has no organization")

    websites = session.get(f"{base}/websites/", headers=headers)
    websites.raise_for_status()
    items = websites.json()
    items = items["results"] if isinstance(items, dict) else items
    website = next(
        (item for item in items if item["domain"] == AUTHORIZED_DOMAIN), None
    )
    if website is None:
        created = session.post(
            f"{base}/websites/",
            headers=headers,
            json={
                "domain": AUTHORIZED_DOMAIN,
                "display_name": "AppChat (authorized live scan)",
                "organization_id": org["id"],
            },
        )
        created.raise_for_status()
        website = created.json()

    if website["domain"] != AUTHORIZED_DOMAIN:
        raise SystemExit(f"refusing unauthorized target: {website['domain']}")

    active = session.get(
        f"{base}/websites/{website['id']}/active_scan/", headers=headers
    )
    if active.status_code == 200:
        raise SystemExit(f"a scan is already active: {active.text[:300]}")

    queued = session.post(
        f"{base}/websites/{website['id']}/scan/",
        headers=headers,
        json={"scan_type": args.scan_type},
    )
    if queued.status_code != 202:
        raise SystemExit(f"scan queue failed ({queued.status_code}): {queued.text[:500]}")
    scan_id = queued.json()["id"]

    report: dict = {
        "target": AUTHORIZED_DOMAIN,
        "website_id": website["id"],
        "organization_id": org["id"],
        "scan_id": scan_id,
        "scan_type": args.scan_type,
        "polls": [],
    }

    deadline = time.monotonic() + args.scan_timeout
    detail: dict = queued.json()
    while time.monotonic() < deadline:
        response = session.get(f"{base}/scans/{scan_id}/", headers=headers)
        response.raise_for_status()
        detail = response.json()
        report["polls"].append(
            {
                "status": detail["status"],
                "progress": detail.get("progress"),
                "current_step": detail.get("current_step"),
            }
        )
        if detail["status"] in {"completed", "failed"}:
            break
        time.sleep(5)

    findings_payload = session.get(
        f"{base}/scans/{scan_id}/findings/", headers=headers
    )
    findings_payload.raise_for_status()
    findings = findings_payload.json()
    findings = findings["results"] if isinstance(findings, dict) else findings

    results_payload = session.get(
        f"{base}/scans/{scan_id}/results/", headers=headers
    )
    results_payload.raise_for_status()
    results = results_payload.json()
    results = results["results"] if isinstance(results, dict) else results

    runs_payload = session.get(
        f"{base}/scans/{scan_id}/scanner-runs/", headers=headers
    )
    runs_payload.raise_for_status()
    runs = runs_payload.json()
    runs = runs["results"] if isinstance(runs, dict) else runs

    report.update(
        {
            "status": detail["status"],
            "progress": detail.get("progress"),
            "duration_seconds": detail.get("duration_seconds"),
            "failure_message": detail.get("failure_message"),
            "check_results": [
                {
                    "category": item["category"],
                    "status": item["status"],
                    "score": item["score"],
                    "summary": item["summary"][:200],
                    "transport": item.get("technical_details", {}).get("transport"),
                    "scanner": item.get("technical_details", {}).get("scanner"),
                }
                for item in results
            ],
            "finding_count": len(findings),
            "findings_by_category": {},
            "findings_by_severity": {},
            "scanner_runs": [
                {
                    "scanner": item["scanner"],
                    "status": item["status"],
                    "duration_ms": item["duration_ms"],
                    "error_message": item.get("error_message", "")[:200],
                    "metadata": item.get("metadata", {}),
                }
                for item in runs
                if item["scanner"] in {"zap", "nuclei"}
            ],
        }
    )
    for finding in findings:
        category = finding["category"]
        severity = finding["severity"]
        report["findings_by_category"][category] = (
            report["findings_by_category"].get(category, 0) + 1
        )
        report["findings_by_severity"][severity] = (
            report["findings_by_severity"].get(severity, 0) + 1
        )

    print(json.dumps(report, indent=2, sort_keys=True))

    categories = {item["category"] for item in results}
    if detail["status"] != "completed":
        raise SystemExit(1)
    if "zap" not in categories or "nuclei" not in categories:
        raise SystemExit("ZAP/Nuclei CheckResult missing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
