from django.urls import path

from .views import PublicScanCreateView, PublicScanDetailView

urlpatterns = [
    path("check/", PublicScanCreateView.as_view(), name="public-check-create"),
    path("check/<str:scan_id>/", PublicScanDetailView.as_view(), name="public-check-detail"),
]
