# Generated for the social connector audit trail.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("integrations", "0002_oauthstate_code_verifier_ciphertext_and_more"),
        ("organizations", "0003_organizationinvitation"),
    ]

    operations = [
        migrations.CreateModel(
            name="SocialAuditEvent",
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
                (
                    "actor_email",
                    models.EmailField(blank=True, default="", max_length=254),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("connected", "Connected"),
                            ("disconnected", "Disconnected"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                (
                    "provider",
                    models.CharField(
                        choices=[
                            ("google", "Google"),
                            ("linkedin", "LinkedIn"),
                            ("facebook", "Facebook"),
                            ("instagram", "Instagram"),
                            ("twitter", "Twitter / X"),
                        ],
                        max_length=32,
                    ),
                ),
                ("external_account_id", models.CharField(max_length=255)),
                ("connection_id", models.UUIDField(blank=True, null=True)),
                (
                    "ip_address",
                    models.GenericIPAddressField(
                        blank=True,
                        null=True,
                        protocol="both",
                        unpack_ipv4=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="social_audit_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="social_audit_events",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "Social audit event",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["organization", "created_at"],
                        name="social_audit_org_created_idx",
                    ),
                    models.Index(
                        fields=["organization", "action"],
                        name="social_audit_org_action_idx",
                    ),
                ],
            },
        ),
    ]
