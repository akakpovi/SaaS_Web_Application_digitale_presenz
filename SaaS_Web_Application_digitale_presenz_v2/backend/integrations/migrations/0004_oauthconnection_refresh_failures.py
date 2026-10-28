from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0003_socialauditevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="oauthconnection",
            name="refresh_failures",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
