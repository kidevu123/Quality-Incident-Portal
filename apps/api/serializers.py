from rest_framework import serializers

from apps.claims.models import Claim, ClaimAttachment, Reimbursement, RMA
from apps.crm.models import Batch, CustomerAccount, Product, SalesOrder
from apps.support.models import Ticket, TicketMessage, TicketStatus


class CustomerAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAccount
        fields = [
            "id",
            "name",
            "external_id",
            "zoho_account_id",
            "sales_volume_ytd",
            "claim_rate_percent",
            "abuse_risk_score",
        ]


class TicketMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketMessage
        fields = ["id", "body", "is_internal", "author_id", "created_at"]


class ClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = Claim
        fields = [
            "id",
            "public_id",
            "po_number",
            "invoice_number",
            "resolution_requested",
            "zoho_replacement_so_number",
            "estimated_exposure",
            "created_at",
        ]


class TicketSerializer(serializers.ModelSerializer):
    messages = TicketMessageSerializer(many=True, read_only=True)
    claim = ClaimSerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "public_id",
            "subject",
            "status",
            "priority",
            "assignee_id",
            "customer_account_id",
            "sla_resolution_at",
            "created_at",
            "updated_at",
            "messages",
            "claim",
        ]


class Customer360Serializer(serializers.ModelSerializer):
    open_tickets = serializers.SerializerMethodField()
    recent_claims = serializers.SerializerMethodField()

    class Meta:
        model = CustomerAccount
        fields = [
            "id",
            "name",
            "notes",
            "sales_volume_ytd",
            "claim_rate_percent",
            "abuse_risk_score",
            "open_tickets",
            "recent_claims",
        ]

    def get_open_tickets(self, obj):
        qs = Ticket.objects.filter(customer_account=obj).exclude(
            status__in=[
                TicketStatus.CLOSED,
                TicketStatus.RESOLVED_CREDIT,
                TicketStatus.RESOLVED_REPLACEMENT,
            ],
        )[:25]
        return TicketSerializer(qs, many=True).data

    def get_recent_claims(self, obj):
        qs = Claim.objects.filter(customer_account=obj).order_by("-created_at")[:25]
        return ClaimSerializer(qs, many=True).data
