"""Telegram Bot API webhook for /start deep-link binding and claim pickup from chat."""

from __future__ import annotations

import json
import logging
import re

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.models import Role, User
from apps.claims.models import Claim
from apps.support.models import Ticket
from apps.support.working_on import apply_staff_working_on_signals

from .telegram_link import consume_telegram_link_token
from .telegram_notify import (
    message_body_signals_working_on_claim,
    resolve_ticket_public_id_from_telegram_reply,
    send_telegram_plain_text,
    telegram_reaction_newly_signals_working_on_claim,
)

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"\b(TKT-[A-Za-z0-9-]+|CLM-[A-Za-z0-9-]+)\b", re.I)


def _telegram_staff_can_pick_up_claims(user: User) -> bool:
    if user.is_superuser:
        return True
    return user.role in {
        Role.ADMIN,
        Role.AGENT,
        Role.QUALITY,
        Role.FINANCE,
    }


def _ticket_from_text_tokens(text: str) -> Ticket | None:
    for m in _TOKEN_RE.finditer(text):
        token = m.group(1)
        if token.upper().startswith("TKT"):
            t = Ticket.objects.filter(public_id__iexact=token).first()
            if t:
                return t
        c = Claim.objects.select_related("ticket").filter(public_id__iexact=token).first()
        if c:
            return c.ticket
    return None


def _resolve_ticket_for_telegram_working_on(
    chat_id_str: str, bound_message_id: int | None, text_for_tokens: str
) -> Ticket | None:
    ticket_public_id = None
    if bound_message_id is not None:
        ticket_public_id = resolve_ticket_public_id_from_telegram_reply(chat_id_str, bound_message_id)
    ticket = None
    if ticket_public_id:
        ticket = Ticket.objects.filter(public_id=ticket_public_id).first()
    if ticket is None and text_for_tokens:
        ticket = _ticket_from_text_tokens(text_for_tokens)
    return ticket


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

        reaction_upd = data.get("message_reaction")
        if reaction_upd:
            chat = reaction_upd.get("chat") or {}
            chat_id = chat.get("id")
            if chat_id is None:
                return JsonResponse({"ok": True})
            from_user = reaction_upd.get("user") or {}
            tg_uid = from_user.get("id")
            if tg_uid is None:
                return JsonResponse({"ok": True})
            old_r = reaction_upd.get("old_reaction")
            new_r = reaction_upd.get("new_reaction")
            if not telegram_reaction_newly_signals_working_on_claim(old_r, new_r):
                return JsonResponse({"ok": True})

            linked = User.objects.filter(telegram_chat_id=int(tg_uid), is_active=True).first()
            if linked is None or not _telegram_staff_can_pick_up_claims(linked):
                return JsonResponse({"ok": True})

            mid = reaction_upd.get("message_id")
            chat_id_str = str(chat_id)
            ticket = _resolve_ticket_for_telegram_working_on(
                chat_id_str, int(mid) if mid is not None else None, ""
            )
            signal_body = "👀"
            if ticket:
                apply_staff_working_on_signals(ticket, linked, signal_body, via_telegram=True)
                send_telegram_plain_text(
                    chat_id_str,
                    f"Nexus Resolve: you’re on {ticket.public_id}. Team notified in Nexus + Telegram.",
                    parse_mode=None,
                )
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

        # 👁 / 👀 in Telegram: same workflow as ticket workspace (reply to bot alert, or include TKT-/CLM-).
        from_user = msg.get("from") or {}
        tg_uid = from_user.get("id")
        if tg_uid is None or not text:
            return JsonResponse({"ok": True})

        linked = User.objects.filter(telegram_chat_id=int(tg_uid), is_active=True).first()
        if linked is None or not _telegram_staff_can_pick_up_claims(linked):
            return JsonResponse({"ok": True})

        if not message_body_signals_working_on_claim(text):
            return JsonResponse({"ok": True})

        chat_id_str = str(chat_id)
        reply_to = msg.get("reply_to_message") or {}
        reply_mid = reply_to.get("message_id")
        reply_mid_int = int(reply_mid) if reply_mid is not None else None
        ticket = _resolve_ticket_for_telegram_working_on(chat_id_str, reply_mid_int, text)

        if ticket:
            apply_staff_working_on_signals(ticket, linked, text, via_telegram=True)
            send_telegram_plain_text(
                chat_id_str,
                f"Nexus Resolve: you’re on {ticket.public_id}. Team notified in Nexus + Telegram.",
                parse_mode=None,
            )
        else:
            send_telegram_plain_text(
                chat_id_str,
                "Nexus Resolve: react with 👁 or 👀 on the bot’s alert, reply with those emojis, or send e.g. “👀 TKT-…-…” / “CLM-…-…” so we know which ticket.",
                parse_mode=None,
            )

        return JsonResponse({"ok": True})
