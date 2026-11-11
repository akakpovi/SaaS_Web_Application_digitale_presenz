"""Run a real security scan and report per-scanner evidence.

This command exists to validate the advanced scanners against an **authorized**
target with the real pipeline (orchestrator → hardened sandbox containers →
archive → findings), and to print only what was actually observed.

It never fabricates a result: every number it reports comes from the database
rows the pipeline wrote, and a scanner that did not run is reported as
``not_run`` rather than silently omitted.

Usage::

    docker compose exec -T web python manage.py validate_advanced_scanners \\
        --domain appchat.elomaiapp.com --runs 2

The target must be owned/authorized by the operator: this command performs real
network scans (port scan, TLS analysis, directory enumeration).
"""

from __future__ import annotations

import json
import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from scans.models import Scan, ScannerRun
from scans.services.orchestrator import ScanOrchestrator
from websites.models import Website

ADVANCED = ("nmap", "nikto", "whatweb", "testssl", "dnsrecon", "gobuster")

OWNER_EMAIL = "validation-owner@presence.local"
OWNER_PASSWORD = "Validation-Only-1!"  # noqa: S105 - local validation account


class Command(BaseCommand):
    help = (
        "Run a real security scan of an authorized target and print per-scanner "
        "status, duration, completeness and archive evidence."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--domain", required=True, help="Authorized target domain")
        parser.add_argument(
            "--scan-type",
            default="security",
            choices=("security", "full", "health"),
            help="Scan type to run (default: security → the six advanced tools)",
        )
        parser.add_argument("--runs", type=int, default=1, help="How many scans to run")
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print one JSON document instead of the human summary",
        )

    def handle(self, *args, **options) -> None:
        domain = options["domain"].strip().lower()
        scan_type = options["scan_type"]
        runs = max(1, int(options["runs"]))

        user, website = self._ensure_asset(domain)
        summaries = []
        for index in range(runs):
            summaries.append(self._run_once(website, scan_type, index + 1))

        if options["json"]:
            self.stdout.write(json.dumps(summaries, indent=2, default=str))
            return

        for summary in summaries:
            self._print_summary(summary)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _ensure_asset(self, domain: str) -> tuple[User, Website]:
        """Return (user, website) for the validation target, creating them once.

        The website is attached to the owner's personal organization, exactly
        as the API does: the ingestion pipeline only records tenant-scoped
        findings for organization-owned sites, so an orphan website would make
        the validation silently meaningless.
        """
        from organizations.services import ensure_personal_organization

        with transaction.atomic():
            user = User.objects.filter(email=OWNER_EMAIL).first()
            if user is None:
                user = User.objects.create_user(OWNER_EMAIL, OWNER_PASSWORD)
            organization = ensure_personal_organization(user)
            website = (
                Website.objects.filter(domain=domain, owner=user).first()
                or Website.objects.filter(domain=domain).first()
            )
            if website is None:
                website = Website.objects.create(
                    owner=user,
                    domain=domain,
                    organization=organization,
                )
            elif website.organization_id is None:
                website.organization = organization
                website.save(update_fields=["organization", "updated_at"])
        return user, website

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _run_once(self, website: Website, scan_type: str, index: int) -> dict[str, Any]:
        scan = Scan.objects.create(
            website=website,
            scan_type=scan_type,
            status=Scan.Status.QUEUED,
        )
        started = time.monotonic()
        ScanOrchestrator(scan.id).run()
        wall_seconds = round(time.monotonic() - started, 1)

        scan.refresh_from_db()
        runs = list(ScannerRun.objects.filter(scan=scan).order_by("started_at", "id"))
        steps = {step.get("scanner"): step for step in (scan.steps or [])}

        per_scanner = []
        for run in runs:
            metadata = run.metadata or {}
            archive = metadata.get("archive") or {}
            per_scanner.append(
                {
                    "scanner": run.scanner,
                    "status": run.status,
                    "step_status": (steps.get(run.scanner) or {}).get("status"),
                    "duration_ms": run.duration_ms,
                    "exit_code": (run.metadata or {}).get("exit_code"),
                    "scan_complete": metadata.get("scan_complete"),
                    "partial_reason": metadata.get("partial_reason"),
                    "findings": run.findings.count(),
                    "archive_status": archive.get("status"),
                    "archive_path": archive.get("path") or archive.get("relative_path"),
                }
            )

        return {
            "run": index,
            "scan_id": scan.id,
            "scan_type": scan_type,
            "target": website.domain,
            "scan_status": scan.status,
            "failure_message": scan.failure_message,
            "progress": scan.progress,
            "wall_seconds": wall_seconds,
            "scanners": per_scanner,
        }

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def _print_summary(self, summary: dict[str, Any]) -> None:
        self.stdout.write(
            f"\n=== scan {summary['scan_id']} ({summary['scan_type']}) "
            f"target={summary['target']} status={summary['scan_status']} "
            f"wall={summary['wall_seconds']}s ==="
        )
        if summary["failure_message"]:
            self.stdout.write(f"  failure: {summary['failure_message']}")
        for entry in summary["scanners"]:
            if entry["scanner"] not in ADVANCED:
                continue
            self.stdout.write(
                "  {scanner:<9} run={status:<11} step={step_status:<11} "
                "complete={scan_complete!s:<5} reason={partial_reason!r:<20} "
                "exit={exit_code!s:<5} {duration_ms:>6} ms findings={findings:<3} "
                "archive={archive_status}".format(**entry)
            )
        missing = sorted(
            set(ADVANCED) - {entry["scanner"] for entry in summary["scanners"]}
        )
        if missing:
            self.stdout.write(f"  not_run: {', '.join(missing)}")
