from rest_framework import serializers
from social.models import SocialProfile, SocialEngagement, SocialMention


class SocialProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialProfile
        fields = "__all__"


class SocialEngagementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialEngagement
        fields = "__all__"


class SocialMentionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialMention
        fields = "__all__"
