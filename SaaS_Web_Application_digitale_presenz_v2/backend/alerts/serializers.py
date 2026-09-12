from rest_framework import serializers

from alerts.models import Alert, AlertPreference, AlertRule, MuteWindow
from websites.models import Website


class AlertSerializer(serializers.ModelSerializer):
    website_domain = serializers.CharField(source="website.domain", read_only=True)

    class Meta:
        model = Alert
        fields = [
            "id", "website_id", "website_domain", "scan_id",
            "alert_type", "severity", "status",
            "title", "message", "metadata",
            "notification_channels_sent",
            "acknowledged_at", "acknowledged_by_id",
            "resolved_at", "created_at", "updated_at",
        ]
        read_only_fields = fields


class AlertPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertPreference
        exclude = ["user", "id"]

    def validate(self, attrs):
        start = attrs.get(
            "quiet_hours_start",
            self.instance.quiet_hours_start if self.instance else None,
        )
        end = attrs.get(
            "quiet_hours_end",
            self.instance.quiet_hours_end if self.instance else None,
        )
        if bool(start) != bool(end):
            raise serializers.ValidationError(
                "quiet_hours_start and quiet_hours_end must both be set or both empty."
            )
        return attrs


class AlertRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertRule
        fields = "__all__"
        read_only_fields = ["id", "user", "last_triggered_at", "created_at", "updated_at"]

    def validate_threshold(self, value):
        metric = self.initial_data.get("metric", "")
        if metric == "health_score" and not (0 <= value <= 100):
            raise serializers.ValidationError(
                "health_score threshold must be between 0 and 100."
            )
        return value


class MuteWindowSerializer(serializers.ModelSerializer):
    website_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        source="websites",
        queryset=Website.objects.all(),
        required=False,
    )

    class Meta:
        model = MuteWindow
        fields = [
            "id", "website_ids", "start_at", "end_at",
            "reason", "note", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        if attrs.get("end_at") and attrs.get("start_at"):
            if attrs["end_at"] <= attrs["start_at"]:
                raise serializers.ValidationError("end_at must be after start_at.")
        return attrs
