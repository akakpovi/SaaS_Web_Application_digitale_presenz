from django.db import migrations, models


class Migration(migrations.Migration):
    """Continuous monitoring is opt-in.

    ``0001_initial`` created ``enabled`` with ``default=True``; the model now
    defaults to ``False`` so a website is never scheduled for repeated scans
    before its owner activates monitoring. Only the column default changes —
    existing rows keep their stored value, so nothing is enabled or disabled
    silently by applying this migration.
    """

    dependencies = [
        ("monitoring", "0002_monitoringconfig_scan_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="monitoringconfig",
            name="enabled",
            field=models.BooleanField(default=False),
        ),
    ]
