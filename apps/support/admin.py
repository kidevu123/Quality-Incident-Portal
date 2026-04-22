from django.contrib import admin

from .models import ResponseMacro, Ticket, TicketMessage, TicketQueue


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(TicketQueue)
class TicketQueueAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("public_id", "subject", "status", "priority", "assignee", "updated_at")
    list_filter = ("status", "priority", "queue")
    search_fields = ("public_id", "subject")
    inlines = [TicketMessageInline]
    raw_id_fields = ("customer_account", "assignee", "requester")


@admin.register(ResponseMacro)
class ResponseMacroAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
