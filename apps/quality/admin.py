from django.contrib import admin

from .models import CAPA, Investigation, QualityIncident


class CAPAInline(admin.StackedInline):
    model = CAPA
    extra = 0


@admin.register(QualityIncident)
class QualityIncidentAdmin(admin.ModelAdmin):
    list_display = ("public_id", "batch", "status", "triggered_by_threshold", "opened_at")
    search_fields = ("public_id", "title")


@admin.register(Investigation)
class InvestigationAdmin(admin.ModelAdmin):
    inlines = [CAPAInline]
    list_filter = ("mitigation_status",)
