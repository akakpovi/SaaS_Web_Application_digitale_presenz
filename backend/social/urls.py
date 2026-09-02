from django.urls import path
from social.views import SocialProfileListCreateView, TriggerSocialSyncView, SocialMentionListView

urlpatterns = [
    path("websites/<int:website_id>/social/profiles/", SocialProfileListCreateView.as_view(), name="social-profiles"),
    path("websites/<int:website_id>/social/sync/", TriggerSocialSyncView.as_view(), name="social-sync"),
    path("websites/<int:website_id>/social/mentions/", SocialMentionListView.as_view(), name="social-mentions"),
]
