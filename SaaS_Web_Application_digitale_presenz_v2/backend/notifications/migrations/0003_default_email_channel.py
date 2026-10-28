"""Backfill the default e-mail alert channel for existing users.

Before this migration no user had a ``NotificationChannel`` row, so
``notifications.dispatcher.dispatch_alert`` iterated an empty queryset and
every alert was created without ever notifying anyone.  The signal added in
``notifications/signals.py`` only covers *new* users, so the existing accounts
are provisioned here.
"""

from django.conf import settings
from django.db import migrations


def create_default_email_channels(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    NotificationChannel = apps.get_model("notifications", "NotificationChannel")

    users_with_channel = set(
        NotificationChannel.objects.filter(channel_type="email").values_list(
            "user_id", flat=True
        )
    )

    to_create = [
        NotificationChannel(
            user_id=user.pk,
            channel_type="email",
            name="Email alerts",
            enabled=True,
            config={"email": user.email},
        )
        for user in User.objects.exclude(pk__in=users_with_channel).only("pk", "email")
    ]

    if to_create:
        NotificationChannel.objects.bulk_create(to_create, batch_size=500)


def delete_default_email_channels(apps, schema_editor):
    NotificationChannel = apps.get_model("notifications", "NotificationChannel")
    NotificationChannel.objects.filter(
        channel_type="email", name="Email alerts"
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0002_webpushsubscription"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            create_default_email_channels,
            delete_default_email_channels,
        ),
    ]
