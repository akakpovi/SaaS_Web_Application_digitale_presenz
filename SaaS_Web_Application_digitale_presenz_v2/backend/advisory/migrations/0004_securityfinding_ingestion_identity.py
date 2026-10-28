"""Give ``SecurityFinding`` its ingestion identity.

Findings created before the ingestion pipeline existed may already contain
duplicates for the same ``(asset, scanner_source, vulnerability_name)``.  The
constraint cannot be added on top of them, so the migration first keeps the
most recently detected row of each group and drops the rest.  The constraint
is what makes the upsert race-free: two concurrent uploads of the same report
can no longer insert the vulnerability twice.
"""

from django.db import migrations, models


def collapse_duplicate_findings(apps, schema_editor):
    SecurityFinding = apps.get_model("advisory", "SecurityFinding")
    duplicates = (
        SecurityFinding.objects.values(
            "asset_id", "scanner_source", "vulnerability_name"
        )
        .annotate(total=models.Count("id"))
        .filter(total__gt=1)
    )
    for group in duplicates.iterator():
        rows = SecurityFinding.objects.filter(
            asset_id=group["asset_id"],
            scanner_source=group["scanner_source"],
            vulnerability_name=group["vulnerability_name"],
        ).order_by("-detected_at", "-created_at")
        keeper = rows.first()
        rows.exclude(pk=keeper.pk).delete()


def noop(apps, schema_editor):
    """Removing the constraint needs no data change."""


class Migration(migrations.Migration):

    dependencies = [
        ("advisory", "0003_securityfinding"),
    ]

    operations = [
        migrations.RunPython(collapse_duplicate_findings, reverse_code=noop),
        migrations.AddConstraint(
            model_name="securityfinding",
            constraint=models.UniqueConstraint(
                fields=("asset", "scanner_source", "vulnerability_name"),
                name="sec_finding_unique_asset_source_name",
            ),
        ),
    ]
