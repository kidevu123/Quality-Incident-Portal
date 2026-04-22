from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "object_type", "object_id", "actor", "created_at")
    list_filter = ("action", "object_type")
