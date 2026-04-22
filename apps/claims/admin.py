from django.contrib import admin

from .models import Approval, Claim, ClaimAttachment, Reimbursement, RMA


class AttachmentInline(admin.TabularInline):
    model = ClaimAttachment
    extra = 0


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("public_id", "ticket", "customer_account", "product", "resolution_requested")
    search_fields = ("public_id", "po_number", "invoice_number")
    inlines = [AttachmentInline]
    raw_id_fields = ("ticket", "customer_account", "product", "batch", "original_sales_order")


@admin.register(RMA)
class RMAAdmin(admin.ModelAdmin):
    search_fields = ("public_id",)


@admin.register(Reimbursement)
class ReimbursementAdmin(admin.ModelAdmin):
    list_filter = ("status",)


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_filter = ("kind", "state")
