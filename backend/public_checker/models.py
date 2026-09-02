from django.db import models
from django.conf import settings

class PublicLead(models.Model):
    email = models.EmailField(db_index=True)
    url_scanned = models.CharField(max_length=255)
    scan_id = models.CharField(max_length=100, null=True, blank=True)
    email_sent = models.BooleanField(default=False)
    email_delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    converted_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="public_leads",
    )

    class Meta:
        ordering = ["-created_at"]
