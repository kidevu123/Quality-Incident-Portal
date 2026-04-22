"""Evaluate automation rules against tickets / claims (sync, idempotent per save)."""

from typing import Optional

from django.conf import settings

from apps.claims.models import Claim, ClaimAttachment
from apps.support.models import Ticket, TicketMessage, TicketStatus

from .models import AutomationRule


def _claim_exposure(claim: Claim) -> float:
    try:
        return float(claim.estimated_exposure or 0)
    except (TypeError, ValueError):
        return 0.0


def run_automation_for_ticket(ticket: Ticket) -> None:
    claim = getattr(ticket, "claim", None)
    rules = AutomationRule.objects.filter(is_active=True).order_by("priority", "id")
    for rule in rules:
        cond = rule.conditions or {}
        actions = rule.actions or {}
        if not _matches(cond, ticket, claim):
            continue
        _apply_actions(actions, ticket, claim)
        break


def _matches(cond: dict, ticket: Ticket, claim: Optional[Claim]) -> bool:
    ctype = cond.get("type")
    if ctype == "small_claim_amount":
        if not claim:
            return False
        max_amt = float(cond.get("max", settings.AUTO_APPROVE_MAX_AMOUNT))
        return _claim_exposure(claim) <= max_amt
    if ctype == "missing_attachments":
        if not claim:
            return False
        return not ClaimAttachment.objects.filter(claim=claim).exists()
    if ctype == "shipping_damage":
        if not claim:
            return False
        from apps.claims.models import DefectType

        return claim.defect_type == DefectType.SHIPPING
    if ctype == "repeat_batch":
        if not claim or not claim.batch_id:
            return False
        threshold = int(cond.get("threshold", settings.HOT_BATCH_CLAIM_THRESHOLD))
        count = Claim.objects.filter(batch_id=claim.batch_id).count()
        return count >= threshold
    return False


def _apply_actions(actions: dict, ticket: Ticket, claim: Optional[Claim]) -> None:
    for action in actions.get("do", []):
        if action == "auto_approve_reimbursement":
            if claim:
                from apps.claims.models import Reimbursement

                r, _ = Reimbursement.objects.get_or_create(
                    claim=claim,
                    defaults={
                        "requested_amount": claim.estimated_exposure or 0,
                        "approved_amount": claim.estimated_exposure or 0,
                        "status": "approved",
                    },
                )
                r.approved_amount = r.requested_amount or claim.estimated_exposure or 0
                r.status = "approved"
                r.save(update_fields=["approved_amount", "status", "requested_amount"])
        elif action == "request_evidence":
            body = (
                "Thanks for your claim. Please upload photos of the product label, "
                "packaging, and the affected units so we can proceed."
            )
            if not ticket.messages.filter(body=body).exists():
                TicketMessage.objects.create(
                    ticket=ticket,
                    author=None,
                    body=body,
                    is_internal=False,
                )
        elif action == "route_logistics_queue":
            from apps.support.models import TicketQueue

            q, _ = TicketQueue.objects.get_or_create(
                slug="logistics",
                defaults={"name": "Logistics", "description": "Shipping damage routing"},
            )
            ticket.queue = q
            ticket.status = TicketStatus.INVESTIGATING
            ticket.save(update_fields=["queue", "status"])
        elif action == "escalate_quality":
            ticket.status = TicketStatus.ESCALATED
            ticket.save(update_fields=["status"])
        elif action == "set_pending_info":
            ticket.status = TicketStatus.PENDING_INFO
            ticket.save(update_fields=["status"])
