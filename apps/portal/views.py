from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView, TemplateView

from apps.accounts.models import Role
from apps.accounts.permissions import user_has_role
from apps.claims.models import AttachmentKind, Claim, ClaimAttachment
from apps.crm.models import Batch, CustomerAccount, EndCustomer, Manufacturer, Product
from apps.support.models import Ticket, TicketMessage, TicketPriority, TicketStatus
from apps.support.utils import default_sla_resolution_deadline, generate_token

from .forms import ClaimSubmissionForm
from .telegram_notify import notify_telegram_portal_claim


def _product_unit_value_for_exposure(product) -> Decimal:
    """Best available per-unit dollar estimate (Product may only have unit_cost today)."""
    for attr in ("unit_price", "list_price", "msrp"):
        v = getattr(product, attr, None)
        if v is not None and v > 0:
            return Decimal(v)
    cost = getattr(product, "unit_cost", None)
    if cost is not None and cost > 0:
        return Decimal(cost)
    return Decimal("0")


def _portal_estimated_exposure(data: dict, product) -> Decimal:
    """Distributor-entered amount, else catalog per-unit value × affected qty when possible."""
    claimed = data.get("estimated_financial_impact")
    if claimed is not None and claimed > 0:
        return claimed.quantize(Decimal("0.01"))
    qty = int(data.get("quantity_affected") or 0)
    unit = _product_unit_value_for_exposure(product)
    if qty > 0 and unit > 0:
        return (Decimal(qty) * unit).quantize(Decimal("0.01"))
    return Decimal("0")


def _guess_attachment_kind(uploaded_file) -> str:
    ct = (getattr(uploaded_file, "content_type", None) or "").lower()
    name = (getattr(uploaded_file, "name", "") or "").lower()
    if ct.startswith("image/") or name.endswith(
        (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".avif")
    ):
        return AttachmentKind.IMAGE
    if ct.startswith("video/") or name.endswith((".mp4", ".webm", ".mov", ".m4v", ".mkv")):
        return AttachmentKind.VIDEO
    return AttachmentKind.DOCUMENT


class DistributorRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not user_has_role(request.user, Role.DISTRIBUTOR, Role.ADMIN):
            if request.user.is_authenticated:
                return redirect(reverse("support_inbox"))
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path(), login_url=reverse("login"))
        return super().dispatch(request, *args, **kwargs)


class PortalHomeView(LoginRequiredMixin, DistributorRequiredMixin, TemplateView):
    template_name = "portal/home.html"


class PortalClaimListView(LoginRequiredMixin, DistributorRequiredMixin, ListView):
    template_name = "portal/claim_list.html"
    context_object_name = "claims"
    paginate_by = 20

    def get_queryset(self):
        # Demo: distributor sees claims for first linked account or all if admin
        qs = Claim.objects.select_related("ticket", "product", "customer_account")
        if self.request.user.role == Role.ADMIN:
            return qs.order_by("-created_at")
        account = CustomerAccount.objects.order_by("id").first()
        if account:
            return qs.filter(customer_account=account).order_by("-created_at")
        return qs.none()


class PortalClaimSubmitView(LoginRequiredMixin, DistributorRequiredMixin, FormView):
    template_name = "portal/claim_submit.html"
    form_class = ClaimSubmissionForm
    success_url = reverse_lazy("portal_claims")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["customer_account_suggestions"] = list(
            CustomerAccount.objects.order_by("name").values_list("name", flat=True)[:800]
        )
        ctx["product_sku_suggestions"] = list(
            Product.objects.order_by("sku").values_list("sku", flat=True)[:2000]
        )
        ctx["batch_lot_suggestions"] = list(
            Batch.objects.order_by("-manufactured_on").values_list("lot_number", flat=True)[:1500]
        )
        return ctx

    def form_valid(self, form):
        data = form.cleaned_data
        account = form._resolved_customer_account
        product = form._resolved_product
        batch = form._resolved_batch
        with transaction.atomic():
            end_customer, _ = EndCustomer.objects.get_or_create(
                distributor=account,
                retailer_name=data["retailer_name"],
                defaults={
                    "contact_name": data.get("contact_name") or "",
                    "email": data.get("contact_email") or "",
                    "phone": data.get("contact_phone") or "",
                },
            )
            ticket = Ticket.objects.create(
                public_id=generate_token("TKT"),
                subject=f"Claim — {product.sku}",
                status=TicketStatus.NEW,
                priority=TicketPriority.NORMAL,
                requester=self.request.user,
                customer_account=account,
                sla_resolution_at=default_sla_resolution_deadline(TicketPriority.NORMAL),
            )
            claim = Claim.objects.create(
                public_id=generate_token("CLM"),
                ticket=ticket,
                customer_account=account,
                end_customer=end_customer,
                po_number=data.get("po_number") or "",
                invoice_number=data.get("invoice_number") or "",
                product=product,
                batch=batch,
                date_sold=data.get("date_sold"),
                defect_type=data["defect_type"],
                quantity_sold=data.get("quantity_sold") or 0,
                quantity_affected=data.get("quantity_affected") or 0,
                severity=data["severity"],
                damage_description=data.get("damage_description") or "",
                suspected_root_cause_customer=data.get("suspected_root_cause_customer") or "",
                resolution_requested=data["resolution_requested"],
                estimated_exposure=_portal_estimated_exposure(data, product),
            )
            for f in self.request.FILES.getlist("attachments"):
                ClaimAttachment.objects.create(
                    claim=claim,
                    file=f,
                    kind=_guess_attachment_kind(f),
                    uploaded_by=self.request.user,
                )
            TicketMessage.objects.create(
                ticket=ticket,
                author=self.request.user,
                body="Claim submitted via distributor portal.",
                is_internal=False,
            )
        from apps.automation.engine import run_automation_for_ticket

        run_automation_for_ticket(ticket)
        notify_telegram_portal_claim(claim, ticket, self.request.user)
        messages.success(self.request, f"Claim {claim.public_id} submitted.")
        return super().form_valid(form)


class PortalTicketThreadView(LoginRequiredMixin, DistributorRequiredMixin, View):
    def get(self, request, public_id):
        ticket = get_object_or_404(Ticket, public_id=public_id)
        claim = getattr(ticket, "claim", None)
        return render(
            request,
            "portal/ticket_thread.html",
            {
                "ticket": ticket,
                "claim": claim,
                "messages": ticket.messages.all(),
                "ticket_status_poll_url": reverse("portal_ticket_status", kwargs={"public_id": public_id}),
            },
        )

    def post(self, request, public_id):
        ticket = get_object_or_404(Ticket, public_id=public_id)
        body = (request.POST.get("body") or "").strip()
        if body:
            TicketMessage.objects.create(
                ticket=ticket,
                author=request.user,
                body=body,
                is_internal=False,
            )
        return redirect("portal_ticket", public_id=public_id)


class PortalTicketStatusView(LoginRequiredMixin, DistributorRequiredMixin, View):
    """JSON for distributor thread page — status refreshes when staff updates the ticket."""

    def get(self, request, public_id):
        ticket = get_object_or_404(
            Ticket.objects.only("public_id", "status", "updated_at"),
            public_id=public_id,
        )
        return JsonResponse(
            {
                "status": ticket.status,
                "label": str(ticket.get_status_display()),
            }
        )
