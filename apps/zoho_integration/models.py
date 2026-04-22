from django.db import models

from apps.claims.models import Claim


class ZohoSyncLog(models.Model):
    class Action(models.TextChoices):
        REPLACEMENT_SO = "replacement_so", "Replacement sales order"
        CREDIT_MEMO = "credit_memo", "Credit memo"
        ACCOUNT_SYNC = "account_sync", "Account sync"
        ORDER_SYNC = "order_sync", "Order sync"
        INVOICE_SYNC = "invoice_sync", "Invoice sync"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        RETRYING = "retrying", "Retrying"

    claim = models.ForeignKey(
        Claim,
        on_delete=models.CASCADE,
        related_name="zoho_logs",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    idempotency_key = models.CharField(max_length=128, unique=True, db_index=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class ZohoPushDedupe(models.Model):
    """Prevent duplicate Zoho pushes for the same claim + action."""

    fingerprint = models.CharField(max_length=64, unique=True, db_index=True)
    zoho_document_number = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
