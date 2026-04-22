from django.urls import path

from . import views

urlpatterns = [
    path("", views.PortalHomeView.as_view(), name="portal_home"),
    path("claims/", views.PortalClaimListView.as_view(), name="portal_claims"),
    path("claims/new/", views.PortalClaimSubmitView.as_view(), name="portal_claim_submit"),
    path("tickets/<str:public_id>/", views.PortalTicketThreadView.as_view(), name="portal_ticket"),
]
