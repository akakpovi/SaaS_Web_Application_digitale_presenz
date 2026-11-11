import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="plan",
            name="tier",
            field=models.CharField(
                choices=[
                    ("free", "Free"),
                    ("pro", "Pro"),
                    ("business", "Business"),
                    ("agency", "Agency"),
                ],
                max_length=10,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="plan",
            name="external_price_id_monthly",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Provider price ID for the monthly cycle (e.g. pri_...)",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="plan",
            name="external_price_id_yearly",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Provider price ID for the yearly cycle (e.g. pri_...)",
                max_length=255,
            ),
        ),
        migrations.CreateModel(
            name="BillingEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("provider", models.CharField(max_length=50)),
                ("event_id", models.CharField(max_length=255)),
                ("event_type", models.CharField(blank=True, max_length=100)),
                ("payload", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("received", "Received"),
                            ("processed", "Processed"),
                            ("failed", "Failed"),
                        ],
                        default="received",
                        max_length=12,
                    ),
                ),
                ("error", models.TextField(blank=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Billing Event",
                "ordering": ["-received_at"],
                "indexes": [
                    models.Index(
                        fields=["provider", "event_type"],
                        name="billing_event_provider_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["provider", "event_id"],
                        name="unique_billing_event_per_provider",
                    )
                ],
            },
        ),
    ]
