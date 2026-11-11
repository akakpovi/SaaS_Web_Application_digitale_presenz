from rest_framework import serializers
from advanced_security.models import SecurityIncident


class SecurityIncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityIncident
        fields = "__all__"
