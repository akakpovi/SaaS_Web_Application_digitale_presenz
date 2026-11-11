from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="monitoringconfig",
            name="scan_type",
            field=models.CharField(
                choices=[
                    ("health", "Health checks only"),
                    ("security", "Security scanners (ZAP, Nuclei, …)"),
                    ("full", "Health + security"),
                ],
                default="health",
                help_text="Scan type launched by the scheduler for this website.",
                max_length=16,
            ),
        ),
    ]
