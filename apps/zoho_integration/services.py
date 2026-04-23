"""Business orchestration for Zoho pushes — approvals, dedupe, audit, logging."""

from __future__ import annotations

import hashlib
import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from apps.accounts.models import Role
from apps.auditlog.services import write_audit
from apps.claims.models import Approval, Claim
from apps.support.models import Ticket, TicketMessage, TicketStatus
from apps.zoho_integration.client import ZohoAPIError, ZohoClient, create_inventory_sales_order_payload
from apps.zoho_integration.models import ZohoPushDedupe, ZohoSyncLog

logger = logging.getLogger(__name__)


def _fingerprint(claim: Claim, action: str) -> str:
    raw = f"{claim.id}|{action}|{claim.product_id}|{claim.quantity_affected}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


@transaction.atomic
def clear_simulated_replacement_so(*, claim: Claim, ticket: Ticket) -> bool:
    """
    Undo a mistaken “Create replacement SO” when Zoho is not configured (SIM-SO-… numbers).
    Clears dedupe so staff can retry after configuring Zoho; removes replacement sync logs.
    """
    so = (claim.zoho_replacement_so_number or "").strip()
    if not so.startswith("SIM-SO-"):
        return False
    fp = _fingerprint(claim, "replacement_so")
    ZohoPushDedupe.objects.filter(fingerprint=fp).delete()
    ZohoSyncLog.objects.filter(claim=claim, action=ZohoSyncLog.Action.REPLACEMENT_SO).delete()
    claim.zoho_replacement_so_number = ""
    claim.save(update_fields=["zoho_replacement_so_number", "updated_at"])
    if ticket.status == TicketStatus.RESOLVED_REPLACEMENT:
        ticket.status = TicketStatus.OPEN
        ticket.save(update_fields=["status", "updated_at"])
    return True


def replacement_so_requires_approval(claim: Claim) -> bool:
    exposure = float(claim.estimated_exposure or 0)
    return exposure >= float(settings.ZOHO_REPLACEMENT_SO_THRESHOLD)


@transaction.atomic
def create_replacement_sales_order(*, claim: Claim, actor) -> ZohoSyncLog:
    if ZohoPushDedupe.objects.filter(fingerprint=_fingerprint(claim, "replacement_so")).exists():
        raise ValueError("Duplicate replacement order already recorded for this claim.")

    if replacement_so_requires_approval(claim):
        approved = Approval.objects.filter(
            claim=claim,
            kind=Approval.Kind.REPLACEMENT_SO,
            state=Approval.State.APPROVED,
        ).exists()
        if not approved and actor.role not in {Role.ADMIN, Role.FINANCE}:
            Approval.objects.get_or_create(
                claim=claim,
                kind=Approval.Kind.REPLACEMENT_SO,
                state=Approval.State.PENDING,
                defaults={
                    "amount_threshold": Decimal(str(settings.ZOHO_REPLACEMENT_SO_THRESHOLD)),
                    "notes": "Auto-created: exceeds replacement threshold",
                },
            )
            raise ValueError("Finance approval required before Zoho SO generation.")

    idem = _fingerprint(claim, "replacement_so") + "-so"
    payload = create_inventory_sales_order_payload(claim)
    log = ZohoSyncLog.objects.create(
        claim=claim,
        action=ZohoSyncLog.Action.REPLACEMENT_SO,
        status=ZohoSyncLog.Status.PENDING,
        idempotency_key=idem[:128],
        request_payload=payload,
    )

    client = ZohoClient()
    try:
        so_number: str
        if not all(
            [
                settings.ZOHO_CLIENT_ID,
                settings.ZOHO_CLIENT_SECRET,
                settings.ZOHO_REFRESH_TOKEN,
            ]
        ):
            so_number = f"SIM-SO-{claim.public_id}"
            log.status = ZohoSyncLog.Status.SUCCESS
            log.response_payload = {"simulated": True, "salesorder_number": so_number}
            log.save(update_fields=["status", "response_payload", "updated_at"])
        else:
            org = settings.ZOHO_ORG_ID
            data = client.request(
                "POST",
                "/inventory/v1/salesorders",
                params={"organization_id": org},
                json=payload,
            )
            so_number = str(
                data.get("salesorder", {}).get("salesorder_number")
                or data.get("salesorder_number")
                or data.get("salesorder_id")
                or "UNKNOWN",
            )
            log.status = ZohoSyncLog.Status.SUCCESS
            log.response_payload = data
            log.save(update_fields=["status", "response_payload", "updated_at"])

        claim.zoho_replacement_so_number = so_number
        claim.save(update_fields=["zoho_replacement_so_number", "updated_at"])

        ticket = claim.ticket
        ticket.status = TicketStatus.RESOLVED_REPLACEMENT
        ticket.save(update_fields=["status", "updated_at"])

        TicketMessage.objects.create(
            ticket=ticket,
            author=actor,
            body=f"Replacement sales order created in Zoho: {claim.zoho_replacement_so_number}",
            is_internal=True,
        )
        ZohoPushDedupe.objects.create(
            fingerprint=_fingerprint(claim, "replacement_so"),
            zoho_document_number=claim.zoho_replacement_so_number,
        )
        write_audit(
            actor=actor,
            action="zoho.replacement_so",
            object_type="claim",
            object_id=claim.public_id,
            after={"zoho_replacement_so_number": claim.zoho_replacement_so_number},
        )
    except ZohoAPIError as exc:
        logger.exception("Zoho replacement SO failed")
        log.status = ZohoSyncLog.Status.FAILED
        log.error_message = str(exc)
        log.response_payload = exc.payload
        log.attempt_count += 1
        log.save(update_fields=["status", "error_message", "response_payload", "attempt_count", "updated_at"])
        raise
    return log
