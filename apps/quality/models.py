from django.conf import settings
from django.db import models

from apps.claims.models import Claim
from apps.crm.models import Batch, Manufacturer


class QualityIncident(models.Model):
    public_id = models.CharField(max_length=32, unique=True, db_index=True)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="incidents")
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=32, default="open")
    triggered_by_threshold = models.BooleanField(default=False)
    claim_count_at_open = models.PositiveIntegerField(default=0)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]

    def __str__(self) -> str:
        return self.public_id


class Investigation(models.Model):
    incident = models.ForeignKey(
        QualityIncident,
        on_delete=models.CASCADE,
        related_name="investigations",
        null=True,
        blank=True,
    )
    claim = models.ForeignKey(
        Claim,
        on_delete=models.CASCADE,
        related_name="investigations",
        null=True,
        blank=True,
    )
    lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    root_cause_summary = models.TextField(blank=True)
    supplier_attribution = models.ForeignKey(
        Manufacturer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    containment_action = models.TextField(blank=True)
    mitigation_status = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class CAPA(models.Model):
    investigation = models.OneToOneField(
        Investigation,
        on_delete=models.CASCADE,
        related_name="capa",
    )
    corrective_action = models.TextField(blank=True)
    preventive_action = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    due_date = models.DateField(null=True, blank=True)
    effectiveness_review = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "CAPA"
        verbose_name_plural = "CAPAs"
