"""Telegram Bot API webhook for /start deep-link binding."""

from __future__ import annotations

import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.models import User

from .telegram_link import consume_telegram_link_token
from .telegram_notify import send_telegram_plain_text

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class TelegramWebhookView(View):
    http_method_names = ["post", "head", "get"]

    def get(self, request, *args, **kwargs):
        """Some uptime checks use GET; Telegram only POSTs updates."""
        return JsonResponse({"ok": True})

    def head(self, request, *args, **kwargs):
        return JsonResponse({"ok": True})

    def post(self, request, *args, **kwargs):
        expected = (getattr(settings, "TELEGRAM_WEBHOOK_SECRET", None) or "").strip()
        if expected:
            got = request.headers.get("X-Telegram-Bot-Api-Secret-Token") or ""
            if got != expected:
                return JsonResponse({"ok": False}, status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"ok": True})

        msg = data.get("message") or data.get("edited_message")
        if not msg:
            return JsonResponse({"ok": True})

        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        text = (msg.get("text") or "").strip()
        if chat_id is None:
            return JsonResponse({"ok": True})

        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            payload = parts[1].strip() if len(parts) > 1 else ""
            if payload.startswith("nxlink_"):
                uid = consume_telegram_link_token(payload)
                if uid:
                    cid = int(chat_id)
                    User.objects.filter(telegram_chat_id=cid).exclude(pk=uid).update(telegram_chat_id=None)
                    User.objects.filter(pk=uid).update(telegram_chat_id=cid)
                    send_telegram_plain_text(
                        str(cid),
                        "<b>Nexus Resolve</b>\nThis chat is linked to your account. New distributor claim alerts appear here for Support Agent, Quality Manager, Administrator, and superuser roles.",
                        parse_mode="HTML",
                    )
                else:
                    send_telegram_plain_text(
                        str(chat_id),
                        "<b>Nexus Resolve</b>\nLink expired or invalid. Open Telegram settings in Nexus and tap “Open Telegram” again.",
                        parse_mode="HTML",
                    )

        return JsonResponse({"ok": True})
