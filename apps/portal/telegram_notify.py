"""Telegram Bot API: claim alerts and helper sends."""

from __future__ import annotations

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


def send_telegram_plain_text(chat_id: str, text: str) -> None:
    """Single sendMessage; failures logged only."""
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", None) or "").strip()
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
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
    - Plus every superuser or Administrator who linked Telegram (telegram_chat_id)
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
        Q(is_superuser=True) | Q(role=Role.ADMIN),
        telegram_chat_id__isnull=False,
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
    lines = [
        "New claim — distributor portal",
        f"Claim: {claim.public_id}",
        f"Ticket: {ticket.public_id}",
        f"Account: {claim.customer_account.name}",
        f"Product: {claim.product.sku}",
        f"Retailer: {retailer}",
        f"Severity: {claim.get_severity_display()}",
        f"Submitted by: {submitted_by.username}",
    ]
    text = "\n".join(lines)

    for chat_id in chat_ids:
        send_telegram_plain_text(chat_id, text)
