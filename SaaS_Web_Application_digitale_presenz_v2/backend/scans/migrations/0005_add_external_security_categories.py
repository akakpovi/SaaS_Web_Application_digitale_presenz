from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scans", "0004_finding_scannerrun_remove_scan_scan_status_valid_and_more"),
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
                ],
                max_length=32,
            ),
        ),
    ]
