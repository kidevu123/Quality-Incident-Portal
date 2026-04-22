from django.conf import settings
from django.db import models

from apps.crm.models import Batch, CustomerAccount, EndCustomer, Product, SalesOrder
from apps.support.models import Ticket


class DefectType(models.TextChoices):
    QUALITY = "quality", "Product quality"
    PACKAGING = "packaging", "Packaging"
    SHIPPING = "shipping", "Shipping damage"
    SHORT = "short", "Short shipment"
    EXPIRED = "expired", "Expiry / dating"
    OTHER = "other", "Other"


class Severity(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class ResolutionRequested(models.TextChoices):
    CREDIT = "credit", "Credit"
    REPLACEMENT = "replacement", "Replacement order"
    INVESTIGATION = "investigation", "Investigation only"
    RMA = "rma", "Return authorization"


class AttachmentKind(models.TextChoices):
    IMAGE = "image", "Image"
    VIDEO = "video", "Video"
    PACKAGING = "packaging", "Packaging"
    BATCH_LABEL = "batch_label", "Batch label"
    DOCUMENT = "document", "Document"


class Claim(models.Model):
    public_id = models.CharField(max_length=32, unique=True, db_index=True)
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="claim")
    customer_account = models.ForeignKey(
        CustomerAccount,
        on_delete=models.PROTECT,
        related_name="claims",
    )
    end_customer = models.ForeignKey(
        EndCustomer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    po_number = models.CharField(max_length=128, blank=True)
    invoice_number = models.CharField(max_length=128, blank=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="claims")
    batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claims",
    )
    original_sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claims",
    )
    date_sold = models.DateField(null=True, blank=True)
    defect_type = models.CharField(
        max_length=32,
        choices=DefectType.choices,
        default=DefectType.OTHER,
    )
    quantity_sold = models.PositiveIntegerField(default=0)
    quantity_affected = models.PositiveIntegerField(default=0)
    severity = models.CharField(
        max_length=16,
        choices=Severity.choices,
        default=Severity.MEDIUM,
    )
    damage_description = models.TextField(blank=True)
    suspected_root_cause_customer = models.TextField(blank=True)
    resolution_requested = models.CharField(
        max_length=32,
        choices=ResolutionRequested.choices,
        default=ResolutionRequested.INVESTIGATION,
    )
    estimated_exposure = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    zoho_replacement_so_number = models.CharField(max_length=64, blank=True)
    zoho_credit_memo_id = models.CharField(max_length=64, blank=True)
    duplicate_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.public_id


class RMA(models.Model):
    public_id = models.CharField(max_length=32, unique=True, db_index=True)
    claim = models.OneToOneField(Claim, on_delete=models.CASCADE, related_name="rma")
    authorized_quantity = models.PositiveIntegerField(default=0)
    return_instructions = models.TextField(blank=True)
    status = models.CharField(max_length=32, default="authorized")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "RMA"
        verbose_name_plural = "RMAs"


class ClaimAttachment(models.Model):
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="claims/%Y/%m/")
    kind = models.CharField(
        max_length=32,
        choices=AttachmentKind.choices,
        default=AttachmentKind.IMAGE,
    )
    scanned_clean = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)


class Reimbursement(models.Model):
    claim = models.OneToOneField(Claim, on_delete=models.CASCADE, related_name="reimbursement")
    requested_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    approved_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="USD")
    status = models.CharField(max_length=32, default="pending")
    finance_notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_reimbursements",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-approved_at"]


class Approval(models.Model):
    """Generic approval step (replacement SO, credit, high value)."""

    class Kind(models.TextChoices):
        REPLACEMENT_SO = "replacement_so", "Replacement sales order"
        CREDIT_MEMO = "credit_memo", "Credit memo"
        REIMBURSEMENT = "reimbursement", "Reimbursement"

    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="approvals")
    kind = models.CharField(max_length=32, choices=Kind.choices)
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    amount_threshold = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
