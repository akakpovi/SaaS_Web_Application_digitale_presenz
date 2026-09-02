from django.contrib import admin
from .models import SocialProfile, SocialEngagement, SocialMention

admin.site.register(SocialProfile)
admin.site.register(SocialEngagement)
admin.site.register(SocialMention)
