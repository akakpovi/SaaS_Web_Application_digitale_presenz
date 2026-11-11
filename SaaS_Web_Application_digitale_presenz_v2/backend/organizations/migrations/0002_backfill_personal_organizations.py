from django.db import migrations


def _organization_name(user) -> str:
    business_name = (getattr(user, "business_name", "") or "").strip()
    if business_name:
        return business_name[:150]
    email = (getattr(user, "email", "") or "").strip()
    return (email.split("@", 1)[0] or "Personal")[:150]


def backfill(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Organization = apps.get_model("organizations", "Organization")
    Membership = apps.get_model("organizations", "Membership")
    Website = apps.get_model("websites", "Website")

    for user in User.objects.all().iterator():
        organization, created = Organization.objects.get_or_create(
            billing_owner_id=user.pk,
            is_personal=True,
            defaults={"name": _organization_name(user)},
        )
        if created:
            Membership.objects.create(
                organization=organization,
                user_id=user.pk,
                role="owner",
            )
        else:
            Membership.objects.get_or_create(
                organization=organization,
                user_id=user.pk,
                defaults={"role": "owner"},
            )

        Website.objects.filter(
            owner_id=user.pk,
            organization_id__isnull=True,
        ).update(organization_id=organization.pk)


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0001_initial"),
        ("websites", "0005_website_organization"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
