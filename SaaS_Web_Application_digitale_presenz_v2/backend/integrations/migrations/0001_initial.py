# Generated for the connector vault.  Kept explicit so the partial unique
# constraint and index names are reviewable in the migration itself.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0003_organizationinvitation"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationDataKey",
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
                ("version", models.PositiveIntegerField()),
                ("wrapped_dek", models.TextField()),
                ("kek_version", models.PositiveIntegerField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("rotated_at", models.DateTimeField(blank=True, null=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="connector_data_keys",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "Organization connector data key",
                "ordering": ["organization", "version"],
                "indexes": [
                    models.Index(
                        fields=["organization", "is_active"],
                        name="conn_dek_org_active_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("organization", "version"),
                        name="uniq_conn_dek_org_version",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("is_active", True)),
                        fields=("organization",),
                        name="unique_active_dek_per_org",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="OAuthConnection",
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
                ("access_token_ciphertext", models.TextField()),
                (
                    "refresh_token_ciphertext",
                    models.TextField(blank=True, default=""),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("expired", "Expired"),
                            ("revoked", "Revoked"),
                            ("error", "Error"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=16,
                    ),
                ),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("key_version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="oauth_connections",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "OAuth connection",
                "ordering": [
                    "organization",
                    "provider",
                    "external_account_id",
                ],
                "indexes": [
                    models.Index(
                        fields=["organization", "provider", "status"],
                        name="oauth_conn_org_prov_status_idx",
                    ),
                    models.Index(
                        fields=["status", "expires_at"],
                        name="oauth_conn_status_expires_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "organization",
                            "provider",
                            "external_account_id",
                        ),
                        name="uniq_oauth_conn_account",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="OAuthState",
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
                ("state_hash", models.CharField(max_length=64, unique=True)),
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
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="oauth_states",
                        to="organizations.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="oauth_states",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "OAuth state",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["organization", "provider"],
                        name="oauth_state_org_provider_idx",
                    ),
                    models.Index(
                        fields=["expires_at"],
                        name="oauth_state_expires_idx",
                    ),
                ],
            },
        ),
    ]
