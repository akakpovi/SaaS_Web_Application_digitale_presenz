from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scans", "0002_scan_add_pending_status"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="scan",
                    name="is_guest",
                    field=models.BooleanField(db_index=True, default=False),
                ),
                migrations.AddField(
                    model_name="scan",
                    name="session_key",
                    field=models.CharField(
                        blank=True, db_index=True, max_length=40, null=True
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE scans_scan ADD COLUMN IF NOT EXISTS is_guest boolean DEFAULT false;
                    ALTER TABLE scans_scan ADD COLUMN IF NOT EXISTS session_key varchar(40);
                    """,
                    reverse_sql="""
                    ALTER TABLE scans_scan DROP COLUMN IF EXISTS is_guest;
                    ALTER TABLE scans_scan DROP COLUMN IF EXISTS session_key;
                    """,
                )
            ],
        )
    ]
