from django.contrib import admin

from .models import TelegramTeamInboxSettings


@admin.register(TelegramTeamInboxSettings)
class TelegramTeamInboxSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "team_chat_ids")

    def has_add_permission(self, request):
        return not TelegramTeamInboxSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
