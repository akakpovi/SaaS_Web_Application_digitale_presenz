from django.db import migrations


class Migration(migrations.Migration):
    """Align the BillingEvent index name with the model definition.

    The first version of migration 0002 used a hand-written index name longer
    than Django's 30-character limit, so the model state and the database
    diverged.  Fresh installs get the canonical name from 0002; existing
    databases are renamed here.  The rename is skipped when it is already
    correct, which keeps the migration idempotent.
    """

    dependencies = [
        ("subscriptions", "0003_api_key"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_class
                    WHERE relname = 'subscription_provider_7b1e1c_idx'
                ) AND NOT EXISTS (
                    SELECT 1 FROM pg_class
                    WHERE relname = 'billing_event_provider_idx'
                ) THEN
                    ALTER INDEX subscription_provider_7b1e1c_idx
                        RENAME TO billing_event_provider_idx;
                END IF;
            END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
