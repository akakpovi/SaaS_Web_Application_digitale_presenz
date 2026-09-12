from rest_framework import serializers

from notifications.models import NotificationChannel
from notifications.providers import get_provider


class NotificationChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationChannel
        fields = "__all__"
        read_only_fields = ["id", "user", "created_at", "updated_at"]

    def validate(self, attrs):
        channel_type = attrs.get("channel_type", "")
        config = attrs.get("config", {})
        dummy = NotificationChannel(channel_type=channel_type, config=config)
        provider = get_provider(dummy)
        if provider:
            errors = provider.validate_config()
            if errors:
                raise serializers.ValidationError({"config": errors})
        return attrs
