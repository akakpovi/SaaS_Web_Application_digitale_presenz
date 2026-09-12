# Generated manually for Phase 4 — add is_active field for future monitoring support.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("websites", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="website",
            name="is_active",
            field=models.BooleanField(
                default=True,
                help_text="Whether monitoring is active for this website.",
            ),
        ),
    ]
