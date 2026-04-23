"""When staff signal they're on a ticket (👁 / 👀), update ticket + audit trail + Telegram."""

from __future__ import annotations

from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist

from apps.portal.telegram_notify import (
    message_body_signals_working_on_claim,
    notify_telegram_staff_working_on_ticket,
)
from apps.support.models import Ticket, TicketMessage, TicketStatus


def _acceptance_note_body(ticket: Ticket, username: str) -> str:
    try:
        ticket.claim
    except ObjectDoesNotExist:
        return f"{username} has accepted this ticket and is working on it."
    return f"{username} has accepted this claim and is working on it."


def apply_staff_working_on_signals(ticket: Ticket, user, body: str) -> None:
    """
    If ``body`` contains the working-on emojis:
    - Add an internal note (at most once per user per ticket per ~10 minutes).
    - Move NEW → OPEN so inbox / portal show the ticket as active.
    - Set assignee when still unassigned.
    - Notify team on Telegram (separate rate limit inside notifier).
    """
    if not body or not message_body_signals_working_on_claim(body):
        return
    if not user or not getattr(user, "is_authenticated", False):
        return

    note_key = f"ticket:auto_work_note:v1:{ticket.pk}:{user.pk}"
    if not cache.get(note_key):
        cache.set(note_key, 1, timeout=600)
        TicketMessage.objects.create(
            ticket=ticket,
            author=user,
            body=_acceptance_note_body(ticket, user.get_username()),
            is_internal=True,
        )

    update_fields: list[str] = []
    if ticket.status == TicketStatus.NEW:
        ticket.status = TicketStatus.OPEN
        update_fields.append("status")
    if ticket.assignee_id is None:
        ticket.assignee = user
        update_fields.append("assignee")
    if update_fields:
        update_fields.append("updated_at")
        ticket.save(update_fields=update_fields)

    notify_telegram_staff_working_on_ticket(ticket, user)
