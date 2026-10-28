from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="language",
            field=models.CharField(
                choices=[("en", "English"), ("fr", "Français"), ("de", "Deutsch")],
                default="en",
                max_length=5,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="business_name",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="user",
            name="business_industry",
            field=models.CharField(
                blank=True,
                choices=[
                    ("restaurant", "Restaurant / Café"),
                    ("retail", "Retail"),
                    ("hotel", "Hotel"),
                    ("auto_repair", "Auto Repair"),
                    ("beauty", "Beauty"),
                    ("agency", "Agency"),
                    ("other", "Other"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="business_country",
            field=models.CharField(
                blank=True,
                choices=[
                    ("DE", "Germany"),
                    ("FR", "France"),
                    ("AT", "Austria"),
                    ("CH", "Switzerland"),
                    ("OTHER", "Other"),
                ],
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="timezone",
            field=models.CharField(
                choices=[
                    ("Europe/Berlin", "Europe/Berlin"),
                    ("Europe/Paris", "Europe/Paris"),
                    ("Europe/Vienna", "Europe/Vienna"),
                    ("UTC", "UTC"),
                ],
                default="Europe/Berlin",
                max_length=64,
            ),
        ),
    ]
