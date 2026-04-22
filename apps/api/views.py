from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.crm.models import CustomerAccount
from apps.support.models import Ticket
from apps.zoho_integration.services import create_replacement_sales_order

from .permissions import IsStaffRole
from .serializers import Customer360Serializer, TicketSerializer


class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ticket.objects.select_related("customer_account", "assignee").prefetch_related(
        "messages",
        "claim",
    )
    serializer_class = TicketSerializer
    permission_classes = [IsStaffRole]
    lookup_field = "public_id"

    @action(detail=True, methods=["post"], url_path="zoho/replacement-so")
    def zoho_replacement_so(self, request, public_id=None):
        ticket = self.get_object()
        claim = getattr(ticket, "claim", None)
        if not claim:
            return Response({"detail": "No claim on ticket."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            log = create_replacement_sales_order(claim=claim, actor=request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": log.status, "response": log.response_payload})


class Customer360ViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CustomerAccount.objects.all()
    serializer_class = Customer360Serializer
    permission_classes = [IsStaffRole]
