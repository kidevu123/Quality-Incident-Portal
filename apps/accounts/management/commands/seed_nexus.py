from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.automation.models import AutomationRule
from apps.claims.models import Claim, DefectType, ResolutionRequested, Severity
from apps.crm.models import Batch, CustomerAccount, EndCustomer, Manufacturer, Product, SalesOrder
from apps.support.models import ResponseMacro, Ticket, TicketPriority, TicketQueue, TicketStatus
from apps.support.utils import default_sla_resolution_deadline, generate_token


class Command(BaseCommand):
    help = "Seed demo data for Nexus Resolve"

    def handle(self, *args, **options):
        admin, _ = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@example.com", "role": Role.ADMIN, "is_staff": True, "is_superuser": True},
        )
        admin.set_password("admin123")
        admin.save()

        agent, _ = User.objects.get_or_create(
            username="agent",
            defaults={"email": "agent@example.com", "role": Role.AGENT, "is_staff": True},
        )
        agent.set_password("agent123")
        agent.save()

        dist, _ = User.objects.get_or_create(
            username="distributor",
            defaults={"email": "dist@example.com", "role": Role.DISTRIBUTOR},
        )
        dist.set_password("dist123")
        dist.save()

        mfg, _ = Manufacturer.objects.get_or_create(code="ACME", defaults={"name": "Acme Foods LLC"})
        prod, _ = Product.objects.get_or_create(
            sku="SKU-1001",
            defaults={
                "description": "Premium wholesale unit",
                "manufacturer": mfg,
                "zoho_item_id": "zoho-item-1",
                "unit_cost": Decimal("12.5000"),
            },
        )
        batch, _ = Batch.objects.get_or_create(
            lot_number="LOT-APR-01",
            product=prod,
            defaults={"manufactured_on": timezone.now().date()},
        )

        acct, _ = CustomerAccount.objects.get_or_create(
            name="Metro Wholesale Co.",
            defaults={
                "external_id": "CUST-001",
                "zoho_account_id": "zoho-acct-1",
                "sales_volume_ytd": Decimal("1250000.00"),
                "claim_rate_percent": Decimal("1.2"),
                "abuse_risk_score": 12,
                "notes": "Strategic distributor — prioritize response quality.",
            },
        )

        TicketQueue.objects.get_or_create(
            slug="general",
            defaults={"name": "General", "sort_order": 10},
        )
        TicketQueue.objects.get_or_create(
            slug="logistics",
            defaults={"name": "Logistics", "sort_order": 20},
        )

        ResponseMacro.objects.get_or_create(
            slug="request-photos",
            defaults={
                "name": "Request photos",
                "category": "evidence",
                "body": "Please upload clear photos of the batch label, outer case, and affected units.",
            },
        )

        AutomationRule.objects.get_or_create(
            slug="missing-photos",
            defaults={
                "name": "Missing attachments → request evidence",
                "priority": 10,
                "conditions": {"type": "missing_attachments"},
                "actions": {"do": ["request_evidence", "set_pending_info"]},
            },
        )
        AutomationRule.objects.get_or_create(
            slug="shipping-route",
            defaults={
                "name": "Shipping damage → logistics queue",
                "priority": 20,
                "conditions": {"type": "shipping_damage"},
                "actions": {"do": ["route_logistics_queue"]},
            },
        )

        so, _ = SalesOrder.objects.get_or_create(
            number="SO-77821",
            defaults={
                "customer": acct,
                "zoho_id": "zoho-so-77821",
                "po_number": "PO-991",
                "invoice_number": "INV-4411",
                "ordered_at": timezone.now(),
                "status": "confirmed",
            },
        )

        ticket, _ = Ticket.objects.get_or_create(
            public_id="TKT-2026-DEMO1",
            defaults={
                "subject": "Quality concern — off flavor",
                "status": TicketStatus.INVESTIGATING,
                "priority": TicketPriority.HIGH,
                "customer_account": acct,
                "assignee": agent,
                "sla_resolution_at": default_sla_resolution_deadline(TicketPriority.HIGH),
            },
        )
        end_customer, _ = EndCustomer.objects.get_or_create(
            distributor=acct,
            retailer_name="Corner Market 12",
            defaults={"email": "store@example.com"},
        )
        Claim.objects.get_or_create(
            ticket=ticket,
            defaults={
                "public_id": "CLM-2026-DEMO1",
                "customer_account": acct,
                "end_customer": end_customer,
                "po_number": "PO-991",
                "invoice_number": "INV-4411",
                "product": prod,
                "batch": batch,
                "original_sales_order": so,
                "date_sold": timezone.now().date(),
                "defect_type": DefectType.QUALITY,
                "quantity_sold": 48,
                "quantity_affected": 6,
                "severity": Severity.HIGH,
                "damage_description": "Off odor reported by retailer.",
                "suspected_root_cause_customer": "Possible batch contamination",
                "resolution_requested": ResolutionRequested.REPLACEMENT,
                "estimated_exposure": Decimal("450.00"),
            },
        )

        self.stdout.write(self.style.SUCCESS("Seed complete. Users: admin/admin123, agent/agent123, distributor/dist123"))
