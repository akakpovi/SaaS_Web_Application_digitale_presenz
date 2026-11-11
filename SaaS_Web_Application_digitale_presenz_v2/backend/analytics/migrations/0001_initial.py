from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="TrafficLog",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("path", models.CharField(max_length=500)),
                        ("method", models.CharField(default="GET", max_length=10)),
                        (
                            "ip_hash",
                            models.CharField(
                                blank=True, db_index=True, max_length=64, null=True
                            ),
                        ),
                        ("is_bot", models.BooleanField(db_index=True, default=False)),
                        (
                            "language",
                            models.CharField(blank=True, max_length=10, null=True),
                        ),
                        ("user_agent", models.TextField(blank=True, null=True)),
                        (
                            "referrer",
                            models.CharField(blank=True, max_length=500, null=True),
                        ),
                        ("status_code", models.IntegerField(default=200)),
                        (
                            "created_at",
                            models.DateTimeField(auto_now_add=True, db_index=True),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={"ordering": ["-created_at"]},
                ),
                migrations.CreateModel(
                    name="AnalyticsEvent",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("event_type", models.CharField(db_index=True, max_length=50)),
                        ("metadata", models.JSONField(blank=True, default=dict)),
                        (
                            "created_at",
                            models.DateTimeField(auto_now_add=True, db_index=True),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={"ordering": ["-created_at"]},
                ),
                migrations.CreateModel(
                    name="AffiliateClick",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("partner", models.CharField(max_length=100)),
                        ("target_url", models.URLField()),
                        (
                            "commission_eur",
                            models.DecimalField(
                                decimal_places=2, default=0.0, max_digits=10
                            ),
                        ),
                        ("converted", models.BooleanField(default=False)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "user",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={"ordering": ["-created_at"]},
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    CREATE TABLE IF NOT EXISTS analytics_trafficlog (
                        id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                        path varchar(500) NOT NULL,
                        method varchar(10) NOT NULL DEFAULT 'GET',
                        ip_hash varchar(64) NULL,
                        is_bot boolean NOT NULL DEFAULT false,
                        language varchar(10) NULL,
                        user_agent text NULL,
                        referrer varchar(500) NULL,
                        status_code integer NOT NULL DEFAULT 200,
                        created_at timestamp with time zone NOT NULL DEFAULT NOW(),
                        user_id bigint NULL REFERENCES accounts_user(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED
                    );
                    ALTER TABLE analytics_trafficlog ADD COLUMN IF NOT EXISTS referrer varchar(500) NULL;
                    CREATE INDEX IF NOT EXISTS analytics_trafficlog_ip_hash_idx ON analytics_trafficlog (ip_hash);
                    CREATE INDEX IF NOT EXISTS analytics_trafficlog_is_bot_idx ON analytics_trafficlog (is_bot);
                    CREATE INDEX IF NOT EXISTS analytics_trafficlog_created_at_idx ON analytics_trafficlog (created_at);

                    CREATE TABLE IF NOT EXISTS analytics_analyticsevent (
                        id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                        event_type varchar(50) NOT NULL,
                        metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                        created_at timestamp with time zone NOT NULL DEFAULT NOW(),
                        user_id bigint NULL REFERENCES accounts_user(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED
                    );

                    CREATE TABLE IF NOT EXISTS analytics_affiliateclick (
                        id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                        partner varchar(100) NOT NULL,
                        target_url varchar(200) NOT NULL,
                        commission_eur numeric(10, 2) NOT NULL DEFAULT 0.0,
                        converted boolean NOT NULL DEFAULT false,
                        created_at timestamp with time zone NOT NULL DEFAULT NOW(),
                        user_id bigint NULL REFERENCES accounts_user(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED
                    );
                    """,
                    reverse_sql="""
                    DROP TABLE IF EXISTS analytics_affiliateclick;
                    DROP TABLE IF EXISTS analytics_analyticsevent;
                    DROP TABLE IF EXISTS analytics_trafficlog;
                    """,
                )
            ],
        )
    ]
