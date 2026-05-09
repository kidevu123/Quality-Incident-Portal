from django.contrib import admin

from .models import Notification, PushSubscription, ResponseMacro, Ticket, TicketMessage, TicketQueue


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


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "kind", "title", "ticket", "is_read", "created_at")
    list_filter = ("kind", "is_read", "created_at")
    search_fields = ("title", "body", "ticket__public_id", "recipient__username")
    autocomplete_fields = ("recipient", "actor", "ticket")


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "is_active", "updated_at", "last_used_at")
    list_filter = ("is_active", "created_at", "updated_at")
    search_fields = ("user__username", "endpoint", "user_agent")
    autocomplete_fields = ("user",)
    readonly_fields = ("endpoint", "p256dh", "auth", "user_agent", "created_at", "updated_at", "last_used_at")


@admin.register(ResponseMacro)
class ResponseMacroAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
