import uuid
from django.db import models
from websites.models import Website


class SecurityIncident(models.Model):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class IncidentType(models.TextChoices):
        MALWARE = "malware", "Malware / Phishing"
        OPEN_PORT = "open_port", "Exposed Port"
        WAF_MISSING = "waf_missing", "No WAF Detected"
        VULNERABILITY = "vulnerability", "Known Vulnerability"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    website = models.ForeignKey(
        Website, on_delete=models.CASCADE, related_name="security_incidents"
    )
    incident_type = models.CharField(max_length=30, choices=IncidentType.choices)
    severity = models.CharField(
        max_length=10, choices=Severity.choices, default=Severity.LOW
    )
    title = models.CharField(max_length=300)
    description = models.TextField()
    evidence = models.JSONField(default=dict, blank=True)
    is_resolved = models.BooleanField(default=False)
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-detected_at"]
        indexes = [models.Index(fields=["website", "is_resolved"])]
