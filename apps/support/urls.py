from django.urls import path

from . import staff_views

urlpatterns = [
    path("", staff_views.SupportInboxEntryView.as_view(), name="support_inbox"),
    path("tickets/<str:public_id>/", staff_views.TicketWorkspaceView.as_view(), name="ticket_workspace"),
    path("customers/<int:pk>/", staff_views.Customer360View.as_view(), name="customer_360"),
    path("dashboard/", staff_views.ExecutiveDashboardView.as_view(), name="executive_dashboard"),
    path("quality/<int:pk>/", staff_views.InvestigationWorkspaceView.as_view(), name="investigation_workspace"),
]
