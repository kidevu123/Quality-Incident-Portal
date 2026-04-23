"""Logged-in Telegram linking UI (deep link to bot)."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.models import User

from .telegram_link import mint_telegram_link_token


class TelegramSettingsView(LoginRequiredMixin, TemplateView):
    template_name = "portal/telegram_settings.html"

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
        return ctx


class TelegramUnlinkView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        User.objects.filter(pk=request.user.pk).update(telegram_chat_id=None)
        messages.success(request, "Telegram unlinked from your account.")
        return redirect("account_telegram")
