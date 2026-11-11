from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scans", "0008_scan_journey_stage_scan_quota_charged_scanjourney_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="checkresult",
            name="category",
            field=models.CharField(
                choices=[
                    ("website", "Website"),
                    ("ssl", "SSL"),
                    ("dns", "DNS"),
                    ("email_security", "Email Security"),
                    ("security_headers", "Security Headers"),
                    ("performance", "Performance"),
                    ("uptime", "Uptime"),
                    ("zap", "OWASP ZAP"),
                    ("nuclei", "Nuclei"),
                    ("exposure", "Exposure"),
                ],
                max_length=32,
            ),
        ),
    ]
