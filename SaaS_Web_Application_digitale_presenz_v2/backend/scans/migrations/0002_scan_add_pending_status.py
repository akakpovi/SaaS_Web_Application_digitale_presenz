# Generated manually for Phase 4 — add pending status and update constraints.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scans", "0001_initial"),
    ]

    operations = [
        # Update the default status from 'queued' to 'pending'.
        migrations.AlterField(
            model_name="scan",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("queued", "Queued"),
                    ("running", "Running"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
        # Drop the old constraint that does not include 'pending'.
        migrations.RemoveConstraint(
            model_name="scan",
            name="scan_status_valid",
        ),
        # Recreate it with 'pending' included.
        migrations.AddConstraint(
            model_name="scan",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "status__in",
                        ["pending", "queued", "running", "completed", "failed"],
                    )
                ),
                name="scan_status_valid",
            ),
        ),
    ]
