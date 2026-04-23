"""Optional Telegram alerts when claims are submitted via the distributor portal."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import requests
from django.conf import settings

if TYPE_CHECKING:
    from apps.claims.models import Claim
    from apps.support.models import Ticket

logger = logging.getLogger(__name__)


def notify_telegram_portal_claim(claim: "Claim", ticket: "Ticket", submitted_by) -> None:
    """
    Send a Telegram message for each configured chat ID.
    If TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_IDS is unset, this is a no-op.
    """
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", None) or "").strip()
    chat_ids = getattr(settings, "TELEGRAM_CHAT_IDS", None) or []
    if not token or not chat_ids:
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
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for raw_id in chat_ids:
        chat_id = str(raw_id).strip()
        if not chat_id:
            continue
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
            logger.exception("Telegram notification failed (chat_id=%s)", chat_id)
