"""Idempotent ingestion of external vulnerability reports.

One uploaded report describes the *current* state of one asset for one
scanner.  The pipeline therefore has three effects, all inside one
transaction:

1. a finding that already exists for ``(asset, scanner_source, name)`` is
   updated in place — its ``detected_at`` is refreshed, its evidence and
   severity replaced, and it is reopened if it had been resolved;
2. a finding that does not exist is created;
3. an ``Open`` finding of that same asset *and* source that is absent from the
   report is marked ``Resolved`` with ``resolved_at`` set, because the scanner
   just proved it is gone.

Scoping is deliberately narrow: the resolution step filters on
``organization``, ``asset`` *and* ``scanner_source``.  A ZAP upload can never
close a Nuclei finding, another asset's finding, or another tenant's finding.

The unique constraint ``sec_finding_unique_asset_source_name`` backs the
identity above so two concurrent uploads cannot create a duplicate; this
service locks the existing rows of the asset/source pair and writes in bulk.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from advisory.models import SecurityFinding
from advisory.parsers import ParsedFinding, ParsedReport

logger = logging.getLogger("advisory.ingestion")

_UPDATABLE_FIELDS = [
    "severity",
    "description",
    "proof_or_payload",
    "status",
    "detected_at",
    "resolved_at",
    "updated_at",
]


class AssetTenantMismatch(ValueError):
    """The asset does not belong to the organization the report targets."""


@dataclass(frozen=True)
class IngestOutcome:
    """Counts returned to the caller (and safe to log: no names, no proof)."""

    source: str
    received: int
    created: int
    updated: int
    resolved: int


def ingest_report(
    organization,
    asset,
    report: ParsedReport,
    *,
    now=None,
    resolve_missing: bool = True,
) -> IngestOutcome:
    """Apply one parsed report to one asset; safe to replay.

    Replaying the same report twice is a no-op for counting purposes: the
    second run updates the same rows and resolves nothing extra.

    ``resolve_missing=False`` disables the resolution step.  Callers pass it
    when the report is known to be *incomplete* (a scan stopped by its timeout,
    a partial run): the scanner did not prove the missing findings are gone, so
    they must stay open.
    """
    if asset.organization_id != organization.pk:
        # Defense in depth: the API already scopes the asset lookup, but this
        # service is also callable from tasks and commands.
        raise AssetTenantMismatch("The asset belongs to another organization.")

    source = report.source
    incoming: dict[str, ParsedFinding] = {}
    for finding in report.findings:
        # The parser already de-duplicates; this keeps the service safe for
        # direct callers that build a ParsedReport themselves.
        incoming.setdefault(finding.vulnerability_name, finding)

    timestamp = now or timezone.now()

    with transaction.atomic():
        existing = {
            finding.vulnerability_name: finding
            for finding in SecurityFinding.objects.select_for_update().filter(
                organization=organization,
                asset=asset,
                scanner_source=source,
            )
        }

        to_create: list[SecurityFinding] = []
        to_update: list[SecurityFinding] = []

        for name, finding in incoming.items():
            current = existing.get(name)
            if current is None:
                to_create.append(
                    SecurityFinding(
                        organization=organization,
                        asset=asset,
                        scanner_source=source,
                        vulnerability_name=name,
                        severity=finding.severity,
                        description=finding.description,
                        proof_or_payload=finding.proof_or_payload,
                        status=SecurityFinding.Status.OPEN,
                        detected_at=timestamp,
                    )
                )
                continue

            current.severity = finding.severity
            current.description = finding.description
            current.proof_or_payload = finding.proof_or_payload
            current.status = SecurityFinding.Status.OPEN
            current.resolved_at = None
            current.detected_at = timestamp
            current.updated_at = timestamp
            to_update.append(current)

        if to_create:
            # ``bulk_create`` skips ``save()``; the organization/asset pair was
            # validated above, which is the invariant ``save()`` would re-check.
            SecurityFinding.objects.bulk_create(to_create)
        if to_update:
            SecurityFinding.objects.bulk_update(to_update, _UPDATABLE_FIELDS)

        resolved = 0
        if resolve_missing:
            resolved = (
                SecurityFinding.objects.filter(
                    organization=organization,
                    asset=asset,
                    scanner_source=source,
                    status=SecurityFinding.Status.OPEN,
                )
                .exclude(vulnerability_name__in=list(incoming))
                .update(
                    status=SecurityFinding.Status.RESOLVED,
                    resolved_at=timestamp,
                    updated_at=timestamp,
                )
            )

    outcome = IngestOutcome(
        source=source,
        received=len(incoming),
        created=len(to_create),
        updated=len(to_update),
        resolved=resolved,
    )
    logger.info(
        "security_report_ingested org=%s asset=%s source=%s received=%s "
        "created=%s updated=%s resolved=%s resolve_missing=%s",
        organization.pk,
        asset.pk,
        outcome.source,
        outcome.received,
        outcome.created,
        outcome.updated,
        outcome.resolved,
        resolve_missing,
    )
    return outcome
