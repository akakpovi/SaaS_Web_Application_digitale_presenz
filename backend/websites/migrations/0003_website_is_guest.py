from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ('websites', '0002_website_is_active'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='website',
                    name='is_guest',
                    field=models.BooleanField(db_index=True, default=False),
                ),
                migrations.AlterField(
                    model_name='website',
                    name='owner',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='websites',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE websites_website ADD COLUMN IF NOT EXISTS is_guest boolean DEFAULT false;
                    ALTER TABLE websites_website ALTER COLUMN owner_id DROP NOT NULL;
                    """,
                    reverse_sql="""
                    ALTER TABLE websites_website DROP COLUMN IF EXISTS is_guest;
                    """
                )
            ]
        )
    ]
