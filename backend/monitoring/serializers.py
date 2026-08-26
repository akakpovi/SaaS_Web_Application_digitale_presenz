from rest_framework import serializers

from monitoring.models import MonitoringConfig


class MonitoringConfigSerializer(serializers.ModelSerializer):
    website_domain = serializers.CharField(source="website.domain", read_only=True)
    website_id = serializers.PrimaryKeyRelatedField(source="website", read_only=True)

    class Meta:
        model = MonitoringConfig
        fields = [
            "id",
            "website_id",
            "website_domain",
            "enabled",
            "interval",
            "last_scan_at",
            "next_scan_at",
            "consecutive_failures",
            "escalation_level",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "website_id",
            "website_domain",
            "last_scan_at",
            "next_scan_at",
            "consecutive_failures",
            "escalation_level",
            "created_at",
            "updated_at",
        ]
