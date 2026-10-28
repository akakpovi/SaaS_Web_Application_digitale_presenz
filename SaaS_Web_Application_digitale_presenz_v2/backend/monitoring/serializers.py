from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from monitoring.models import INTERVAL_MAP, MonitoringConfig


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
            "scan_type",
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

    def update(self, instance, validated_data):
        """Keep the schedule consistent with the activation state.

        * activating schedules the first check immediately;
        * pausing clears the pending schedule so nothing runs afterwards;
        * changing the interval while active re-schedules from now, never in
          the past (which would make the scanner catch up with a burst).
        """
        was_enabled = instance.enabled
        previous_interval = instance.interval

        instance = super().update(instance, validated_data)
        now = timezone.now()
        update_fields: list[str] = []

        if not instance.enabled:
            if instance.next_scan_at is not None:
                instance.next_scan_at = None
                update_fields.append("next_scan_at")
        elif not was_enabled:
            instance.next_scan_at = now
            update_fields.append("next_scan_at")
        elif instance.interval != previous_interval:
            interval = INTERVAL_MAP.get(instance.interval, timedelta(hours=24))
            instance.next_scan_at = now + interval
            update_fields.append("next_scan_at")

        if update_fields:
            instance.save(update_fields=[*update_fields, "updated_at"])

        return instance
