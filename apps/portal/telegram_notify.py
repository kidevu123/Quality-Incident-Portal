"""Telegram Bot API: claim alerts and helper sends."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

import requests
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from apps.accounts.models import Role, User

if TYPE_CHECKING:
    from apps.claims.models import Claim
    from apps.support.models import Ticket

logger = logging.getLogger(__name__)

# Linked Telegram users with these roles (or superuser) get new portal-claim pings.
_PORTAL_CLAIM_NOTIFY_ROLES = (
    Role.ADMIN,
    Role.AGENT,
    Role.QUALITY,
)

# Linked Telegram + env chat IDs for “someone is working this claim” (👁 / 👀 in staff reply).
_STAFF_WORKING_ON_NOTIFY_ROLES = (
    Role.ADMIN,
    Role.AGENT,
    Role.QUALITY,
    Role.FINANCE,
)


def _tg_h(s: str) -> str:
    """Escape text for Telegram HTML parse_mode."""
    return html.escape(s or "", quote=False)


def send_telegram_plain_text(
    chat_id: str, text: str, *, parse_mode: str | None = None
) -> int | None:
    """Single sendMessage; failures logged only. Returns Telegram ``message_id`` when successful."""
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", None) or "").strip()
    if not token or not chat_id:
        return None
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body: dict = {"chat_id": chat_id, "text": text}
    if parse_mode:
        body["parse_mode"] = parse_mode
    try:
        resp = requests.post(url, json=body, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("ok"):
            logger.warning("Telegram sendMessage not ok: %s", payload)
            return None
        result = payload.get("result") or {}
        mid = result.get("message_id")
        return int(mid) if mid is not None else None
    except Exception:  # noqa: BLE001
        logger.exception("Telegram send failed (chat_id=%s)", chat_id)
        return None


TG_REPLY_BIND_CACHE_PREFIX = "tg:reply_bind:v1"
TG_REPLY_BIND_TTL = 60 * 86400  # 60 days — staff can reply to older alerts


def register_telegram_message_for_ticket_reply(chat_id: str, message_id: int, ticket_public_id: str) -> None:
    """So webhook can map \"reply to this bot message\" → ticket ``public_id``."""
    from django.core.cache import cache

    key = f"{TG_REPLY_BIND_CACHE_PREFIX}:{chat_id}:{message_id}"
    cache.set(key, ticket_public_id, timeout=TG_REPLY_BIND_TTL)


def resolve_ticket_public_id_from_telegram_reply(chat_id: str, reply_to_message_id: int | None) -> str | None:
    from django.core.cache import cache

    if reply_to_message_id is None:
        return None
    key = f"{TG_REPLY_BIND_CACHE_PREFIX}:{chat_id}:{reply_to_message_id}"
    val = cache.get(key)
    return str(val).strip() if val else None


def collect_portal_claim_notification_chat_ids() -> list[str]:
    """
    Recipients for new portal claims:
    - TELEGRAM_CHAT_IDS from env (e.g. group chat, or your personal id)
    - Plus every superuser or internal role in _PORTAL_CLAIM_NOTIFY_ROLES who linked Telegram
    """
    ids: list[str] = []
    seen: set[str] = set()

    def add(raw: object) -> None:
        s = str(raw).strip()
        if not s or s in seen:
            return
        seen.add(s)
        ids.append(s)

    for raw in getattr(settings, "TELEGRAM_CHAT_IDS", None) or []:
        add(raw)

    qs = User.objects.filter(
        Q(is_superuser=True) | Q(role__in=_PORTAL_CLAIM_NOTIFY_ROLES),
        telegram_chat_id__isnull=False,
        is_active=True,
    ).values_list("telegram_chat_id", flat=True)
    for cid in qs:
        add(cid)

    return ids


def collect_staff_working_on_claim_chat_ids() -> list[str]:
    """
    Recipients when a staff member signals they are taking a ticket (eye emoji in reply):
    - TELEGRAM_CHAT_IDS
    - Active superusers and roles in _STAFF_WORKING_ON_NOTIFY_ROLES with linked Telegram
    """
    ids: list[str] = []
    seen: set[str] = set()

    def add(raw: object) -> None:
        s = str(raw).strip()
        if not s or s in seen:
            return
        seen.add(s)
        ids.append(s)

    for raw in getattr(settings, "TELEGRAM_CHAT_IDS", None) or []:
        add(raw)

    qs = User.objects.filter(
        Q(is_superuser=True) | Q(role__in=_STAFF_WORKING_ON_NOTIFY_ROLES),
        telegram_chat_id__isnull=False,
        is_active=True,
    ).values_list("telegram_chat_id", flat=True)
    for cid in qs:
        add(cid)

    return ids


def message_body_signals_working_on_claim(body: str) -> bool:
    """True if staff message should broadcast ‘working on this’ (👀 or 👁 in the text)."""
    if not (body and body.strip()):
        return False
    # 👀 U+1F440, 👁 U+1F441 (👁️ uses same base code point)
    return "\U0001f440" in body or "\U0001f441" in body


def _reaction_list_has_working_on_eyes(reactions: list | None) -> bool:
    """True if Bot API ``ReactionType`` list includes 👀 / 👁 (``type`` == ``emoji``)."""
    for r in reactions or []:
        if not isinstance(r, dict):
            continue
        if r.get("type") != "emoji":
            continue
        em = r.get("emoji") or ""
        if "\U0001f440" in em or "\U0001f441" in em:
            return True
    return False


def telegram_reaction_newly_signals_working_on_claim(old_reaction: list | None, new_reaction: list | None) -> bool:
    """True when the user *added* 👀/👁 (present in ``new_reaction`` but not ``old_reaction``)."""
    return _reaction_list_has_working_on_eyes(new_reaction) and not _reaction_list_has_working_on_eyes(
        old_reaction
    )


def notify_telegram_staff_working_on_ticket(ticket: "Ticket", actor) -> None:
    """Tell the team (Telegram) that ``actor`` is working this ticket; skip duplicate within 10 min."""
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", None) or "").strip()
    if not token or not actor or not getattr(actor, "pk", None):
        return

    from django.core.cache import cache

    rl_key = f"tg:work_on:v1:{ticket.pk}:{actor.pk}"
    if cache.get(rl_key):
        return
    cache.set(rl_key, 1, timeout=600)

    chat_ids = collect_staff_working_on_claim_chat_ids()
    if not chat_ids:
        return

    actor_cid = ""
    if getattr(actor, "telegram_chat_id", None):
        actor_cid = str(actor.telegram_chat_id).strip()

    uname = actor.get_username() if hasattr(actor, "get_username") else str(actor.pk)
    lines = [
        "<b>👁 On it</b>",
        "",
        f"<b>{_tg_h(uname)}</b> is working this ticket.",
        "",
        f"<code>{_tg_h(ticket.public_id)}</code>",
    ]
    try:
        claim = ticket.claim
    except ObjectDoesNotExist:
        claim = None
    if claim is not None:
        lines.append(f"<code>{_tg_h(claim.public_id)}</code>")

    text = "\n".join(lines)
    for cid in chat_ids:
        if actor_cid and cid == actor_cid:
            continue
        mid = send_telegram_plain_text(cid, text, parse_mode="HTML")
        if mid is not None:
            register_telegram_message_for_ticket_reply(str(cid), mid, ticket.public_id)


def notify_telegram_portal_claim(claim: "Claim", ticket: "Ticket", submitted_by) -> None:
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", None) or "").strip()
    if not token:
        return

    chat_ids = collect_portal_claim_notification_chat_ids()
    if not chat_ids:
        return

    retailer = "—"
    if claim.end_customer_id:
        retailer = claim.end_customer.retailer_name
    sev = claim.get_severity_display()
    # Compact layout: emoji cues, bold highlights, IDs in <code>; user text escaped for HTML.
    text = "\n".join(
        [
            "<b>🔔 New claim</b> · portal",
            "",
            f"<code>{_tg_h(claim.public_id)}</code>",
            f"<code>{_tg_h(ticket.public_id)}</code>",
            "",
            f"🏢 <b>{_tg_h(claim.customer_account.name)}</b>",
            f"📦 <b>{_tg_h(claim.product.sku)}</b>",
            f"🏪 {_tg_h(retailer)}",
            "",
            f"⚠️ <b>{_tg_h(sev)}</b>",
            f"👤 {_tg_h(submitted_by.username)}",
        ]
    )

    for chat_id in chat_ids:
        mid = send_telegram_plain_text(chat_id, text, parse_mode="HTML")
        if mid is not None:
            register_telegram_message_for_ticket_reply(str(chat_id), mid, ticket.public_id)
