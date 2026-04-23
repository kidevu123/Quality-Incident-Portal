from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.db.models import Count, Prefetch, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.accounts.models import Role
from apps.accounts.permissions import user_can_use_distributor_portal, user_has_role
from apps.claims.models import Claim, ClaimAttachment
from apps.crm.models import CustomerAccount
from apps.quality.models import Investigation, QualityIncident
from apps.support.models import Ticket, TicketMessage, TicketStatus
from apps.support.working_on import apply_staff_working_on_signals


class StaffUserMixin(UserPassesTestMixin):
    def test_func(self):
        return user_has_role(
            self.request.user,
            Role.AGENT,
            Role.QUALITY,
            Role.FINANCE,
            Role.ADMIN,
        )

    def handle_no_permission(self):
        # AccessMixin raises PermissionDenied(403) whenever is_authenticated is True unless we
        # return a response here — never call super() for logged-in users.
        user = self.request.user
        if user.is_authenticated:
            if user_has_role(user, Role.AGENT, Role.QUALITY, Role.FINANCE, Role.ADMIN):
                return redirect(reverse("support_inbox"))
            if user_can_use_distributor_portal(user):
                return redirect(reverse("portal_home"))
            return redirect(reverse("no_workspace_access"))
        return redirect_to_login(self.request.get_full_path(), login_url=reverse("login"))


class SupportInboxEntryView(View):
    """
    Routes `/` without UserPassesTestMixin so anonymous and distributors never hit Django's
    authenticated 403 path (see AccessMixin.handle_no_permission).
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url=reverse("login"))
        if not user_has_role(
            request.user,
            Role.AGENT,
            Role.QUALITY,
            Role.FINANCE,
            Role.ADMIN,
        ):
            if user_can_use_distributor_portal(request.user):
                return redirect(reverse("portal_home"))
            return redirect(reverse("no_workspace_access"))
        return SupportInboxView.as_view()(request, *args, **kwargs)


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
        att_qs = ClaimAttachment.objects.select_related("uploaded_by").order_by("created_at")
        return Ticket.objects.select_related("customer_account", "assignee").prefetch_related(
            "messages__author",
            "claim__product__manufacturer",
            "claim__batch",
            "claim__end_customer",
            "claim__reimbursement",
            "claim__zoho_logs",
            Prefetch("claim__attachments", queryset=att_qs),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["ticket_statuses"] = TicketStatus.choices
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.POST.get("action") == "delete_message":
            if not (request.user.is_superuser or request.user.role == Role.ADMIN):
                messages.error(request, "Only administrators can delete internal notes.")
                return redirect(reverse("ticket_workspace", kwargs={"public_id": self.object.public_id}))
            raw_id = request.POST.get("message_id") or ""
            if not str(raw_id).isdigit():
                messages.error(request, "Invalid message.")
                return redirect(reverse("ticket_workspace", kwargs={"public_id": self.object.public_id}))
            msg = get_object_or_404(TicketMessage, pk=int(raw_id), ticket_id=self.object.id)
            if not msg.is_internal:
                messages.error(request, "Only internal notes can be deleted here.")
                return redirect(reverse("ticket_workspace", kwargs={"public_id": self.object.public_id}))
            claim = getattr(self.object, "claim", None)
            zoho_note = msg.body.startswith("Replacement sales order created in Zoho:")
            matched_zoho = bool(
                claim
                and zoho_note
                and (claim.zoho_replacement_so_number or "") in msg.body
            )
            sim_cleared = False
            if matched_zoho:
                from apps.zoho_integration.services import clear_simulated_replacement_so

                sim_cleared = clear_simulated_replacement_so(claim=claim, ticket=self.object)
            msg.delete()
            if matched_zoho and sim_cleared:
                messages.success(
                    request,
                    "Removed the Zoho note and cleared the simulated replacement (ticket set back to Open when it was resolved via replacement).",
                )
            elif matched_zoho and not sim_cleared:
                messages.warning(
                    request,
                    "Note removed. This claim still has a non-simulated Zoho SO on file; clear it in admin if needed.",
                )
            else:
                messages.success(request, "Internal note removed.")
            return redirect(reverse("ticket_workspace", kwargs={"public_id": self.object.public_id}))
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
            apply_staff_working_on_signals(self.object, request.user, body)
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
