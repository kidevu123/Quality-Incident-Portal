from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Sum
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView, ListView, TemplateView

from apps.accounts.models import Role
from apps.accounts.permissions import user_has_role
from apps.claims.models import Claim
from apps.crm.models import CustomerAccount
from apps.quality.models import Investigation, QualityIncident
from apps.support.models import Ticket, TicketMessage, TicketStatus


class StaffUserMixin(UserPassesTestMixin):
    def test_func(self):
        return user_has_role(
            self.request.user,
            Role.AGENT,
            Role.QUALITY,
            Role.FINANCE,
            Role.ADMIN,
        )


class SupportInboxView(LoginRequiredMixin, StaffUserMixin, ListView):
    template_name = "support/inbox.html"
    context_object_name = "tickets"
    paginate_by = 30

    def get_queryset(self):
        return (
            Ticket.objects.select_related("customer_account", "assignee", "queue")
            .prefetch_related("claim")
            .order_by("-updated_at")
        )


class TicketWorkspaceView(LoginRequiredMixin, StaffUserMixin, DetailView):
    model = Ticket
    template_name = "support/ticket_workspace.html"
    context_object_name = "ticket"
    slug_field = "public_id"
    slug_url_kwarg = "public_id"

    def get_queryset(self):
        return Ticket.objects.select_related("customer_account", "assignee").prefetch_related(
            "messages__author",
            "claim__product__manufacturer",
            "claim__batch",
            "claim__reimbursement",
            "claim__zoho_logs",
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["ticket_statuses"] = TicketStatus.choices
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.POST.get("action") == "zoho_replacement":
            from apps.zoho_integration.services import create_replacement_sales_order

            claim = getattr(self.object, "claim", None)
            if claim:
                try:
                    create_replacement_sales_order(claim=claim, actor=request.user)
                    messages.success(request, "Replacement sales order pushed to Zoho.")
                except ValueError as exc:
                    messages.error(request, str(exc))
                except Exception:  # noqa: BLE001
                    messages.error(request, "Zoho push failed — see sync logs.")
            return redirect(reverse("ticket_workspace", kwargs={"public_id": self.object.public_id}))
        body = (request.POST.get("body") or "").strip()
        internal = request.POST.get("internal") == "1"
        if body:
            TicketMessage.objects.create(
                ticket=self.object,
                author=request.user,
                body=body,
                is_internal=internal,
            )
        new_status = request.POST.get("status")
        if new_status and new_status in dict(TicketStatus.choices):
            self.object.status = new_status
            self.object.save(update_fields=["status", "updated_at"])
        return redirect(reverse("ticket_workspace", kwargs={"public_id": self.object.public_id}))


class Customer360View(LoginRequiredMixin, StaffUserMixin, DetailView):
    model = CustomerAccount
    template_name = "support/customer_360.html"
    context_object_name = "account"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        account = self.object
        ctx["open_tickets"] = Ticket.objects.filter(customer_account=account).exclude(
            status__in=[
                TicketStatus.CLOSED,
                TicketStatus.RESOLVED_CREDIT,
                TicketStatus.RESOLVED_REPLACEMENT,
            ],
        )[:50]
        ctx["claims"] = Claim.objects.filter(customer_account=account).select_related("ticket", "product")[:50]
        ctx["claim_stats"] = Claim.objects.filter(customer_account=account).aggregate(
            n=Count("id"),
            exposure=Sum("estimated_exposure"),
        )
        return ctx


class ExecutiveDashboardView(LoginRequiredMixin, StaffUserMixin, TemplateView):
    template_name = "support/dashboard_executive.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["ticket_counts"] = Ticket.objects.values("status").annotate(c=Count("id"))
        ctx["claims_by_sku"] = (
            Claim.objects.values("product__sku")
            .annotate(c=Count("id"))
            .order_by("-c")[:12]
        )
        ctx["hot_batches"] = QualityIncident.objects.filter(status="open").select_related("batch__product")[:12]
        ctx["sla_breached"] = Ticket.objects.filter(sla_breached=True).count()
        ctx["reimbursement_exposure"] = Claim.objects.aggregate(total=Sum("estimated_exposure"))["total"] or 0
        return ctx


class InvestigationWorkspaceView(LoginRequiredMixin, StaffUserMixin, DetailView):
    model = QualityIncident
    template_name = "support/investigation.html"
    context_object_name = "incident"
    pk_url_kwarg = "pk"

    def get_queryset(self):
        return QualityIncident.objects.select_related("batch__product__manufacturer")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        batch = self.object.batch
        ctx["related_claims"] = Claim.objects.filter(batch=batch).select_related("ticket", "customer_account")
        ctx["investigations"] = Investigation.objects.filter(incident=self.object)
        return ctx
