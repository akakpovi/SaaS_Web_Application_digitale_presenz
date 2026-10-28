from django.urls import path

from .views import (
    InvitationAcceptView,
    OrganizationInvitationDetailView,
    OrganizationInvitationListView,
    OrganizationListAPIView,
    OrganizationMemberDetailView,
    OrganizationMemberListCreateView,
)

app_name = "organizations"

urlpatterns = [
    path(
        "organizations/",
        OrganizationListAPIView.as_view(),
        name="organization-list",
    ),
    path(
        "organizations/<uuid:organization_id>/members/",
        OrganizationMemberListCreateView.as_view(),
        name="organization-members",
    ),
    path(
        "organizations/<uuid:organization_id>/members/<uuid:pk>/",
        OrganizationMemberDetailView.as_view(),
        name="organization-member-detail",
    ),
    path(
        "organizations/<uuid:organization_id>/invitations/",
        OrganizationInvitationListView.as_view(),
        name="organization-invitations",
    ),
    path(
        "organizations/<uuid:organization_id>/invitations/<uuid:pk>/",
        OrganizationInvitationDetailView.as_view(),
        name="organization-invitation-detail",
    ),
    path(
        "organizations/invitations/<str:token>/accept/",
        InvitationAcceptView.as_view(),
        name="organization-invitation-accept",
    ),
]
