from django.contrib import admin

from .models import ZohoPushDedupe, ZohoSyncLog


@admin.register(ZohoSyncLog)
class ZohoSyncLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "status", "claim_id", "attempt_count", "created_at")
    list_filter = ("action", "status")


@admin.register(ZohoPushDedupe)
class ZohoPushDedupeAdmin(admin.ModelAdmin):
    search_fields = ("fingerprint", "zoho_document_number")
