"""Telegram Bot API: claim alerts and helper sends."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

import requests
from django.conf import settings
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


def _tg_h(s: str) -> str:
    """Escape text for Telegram HTML parse_mode."""
    return html.escape(s or "", quote=False)


def send_telegram_plain_text(chat_id: str, text: str, *, parse_mode: str | None = None) -> None:
    """Single sendMessage; failures logged only."""
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", None) or "").strip()
    if not token or not chat_id:
        return
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
    except Exception:  # noqa: BLE001
        logger.exception("Telegram send failed (chat_id=%s)", chat_id)


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
        send_telegram_plain_text(chat_id, text, parse_mode="HTML")
