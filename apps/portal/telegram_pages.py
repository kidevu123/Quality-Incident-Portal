"""Logged-in Telegram linking UI (deep link to bot)."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.models import Role, User

from .models import TelegramTeamInboxSettings
from .team_telegram_ids import parse_team_telegram_chat_ids_input
from .telegram_link import mint_telegram_link_token
from .telegram_notify import merged_telegram_broadcast_chat_ids


def _can_edit_team_telegram_inbox(user) -> bool:
    return bool(user.is_superuser or getattr(user, "role", None) == Role.ADMIN)


class InternalTeamTelegramMixin:
    """Telegram alerts are for Nexus staff only — not distributor portal users."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == Role.DISTRIBUTOR:
            messages.info(
                request,
                "Telegram notifications are set up by your Nexus support team. "
                "You will receive updates on your claims in this portal.",
            )
            return redirect("portal_home")
        return super().dispatch(request, *args, **kwargs)


class TelegramSettingsView(InternalTeamTelegramMixin, LoginRequiredMixin, TemplateView):
    template_name = "portal/telegram_settings.html"

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") != "save_team_telegram_inbox":
            return redirect(reverse("account_telegram"))
        if not _can_edit_team_telegram_inbox(request.user):
            messages.error(request, "Only administrators can change the team group inbox.")
            return redirect(reverse("account_telegram"))
        raw_text = request.POST.get("team_telegram_chat_ids", "")
        valid, invalid = parse_team_telegram_chat_ids_input(raw_text)
        if invalid:
            preview = ", ".join(invalid[:8])
            suffix = "…" if len(invalid) > 8 else ""
            messages.error(
                request,
                "Each chat ID must be numeric (optional leading minus). "
                f"Invalid: {preview}{suffix}",
            )
            return redirect(reverse("account_telegram"))
        row = TelegramTeamInboxSettings.load()
        row.team_chat_ids = valid
        row.save(update_fields=["team_chat_ids"])
        messages.success(
            request,
            "Team group inbox saved. Alerts will include these chats, plus any TELEGRAM_CHAT_IDS on the server "
            "and linked staff DMs.",
        )
        return redirect(reverse("account_telegram"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        bot = (getattr(settings, "TELEGRAM_BOT_USERNAME", None) or "").strip().lstrip("@")
        ctx["telegram_bot_configured"] = bool(
            (getattr(settings, "TELEGRAM_BOT_TOKEN", None) or "").strip() and bot
        )
        ctx["telegram_bot_username"] = bot
        ctx["telegram_linked"] = self.request.user.telegram_chat_id is not None
        if ctx["telegram_bot_configured"]:
            token = mint_telegram_link_token(self.request.user.pk)
            ctx["telegram_deep_link"] = f"https://t.me/{bot}?start={token}"
        else:
            ctx["telegram_deep_link"] = ""
        ctx["webhook_url"] = self.request.build_absolute_uri(reverse("telegram_webhook"))
        inbox = TelegramTeamInboxSettings.load()
        portal_ids = inbox.team_chat_ids or []
        ctx["team_telegram_chat_ids_field"] = ", ".join(str(x) for x in portal_ids)
        ctx["can_edit_team_telegram_inbox"] = _can_edit_team_telegram_inbox(self.request.user)
        ctx["telegram_broadcast_chat_count"] = len(merged_telegram_broadcast_chat_ids())
        ctx["telegram_env_chat_count"] = len(getattr(settings, "TELEGRAM_CHAT_IDS", None) or [])
        ctx["telegram_portal_team_inbox_count"] = len(portal_ids)
        return ctx


class TelegramUnlinkView(InternalTeamTelegramMixin, LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        User.objects.filter(pk=request.user.pk).update(telegram_chat_id=None)
        messages.success(request, "Telegram unlinked from your account.")
        return redirect("account_telegram")
