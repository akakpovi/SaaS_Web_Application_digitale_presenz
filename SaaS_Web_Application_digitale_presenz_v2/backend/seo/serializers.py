from rest_framework import serializers
from seo.models import SEOAudit, Keyword, Backlink


class SEOAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = SEOAudit
        fields = "__all__"


class KeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = Keyword
        fields = "__all__"


class BacklinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Backlink
        fields = "__all__"
