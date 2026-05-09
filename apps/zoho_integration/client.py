"""Zoho proxy client.

All Zoho API calls flow through the centralized zoho-integration-service
(LXC 9503 at http://192.168.1.205:8000). The proxy handles OAuth refresh,
brand → org_id resolution, audit logging, and rate limiting. Nexus only
needs to know:

  - the proxy URL,
  - which brand it's calling on behalf of (haute_brands),
  - the internal token shared between all internal apps and the proxy.

That's it. No more per-app Zoho client_id / client_secret / refresh_token.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ZohoAPIError(Exception):
    """Raised when the proxy returns 4xx/5xx or is unreachable."""

    def __init__(self, message: str, status: Optional[int] = None, payload: Optional[Dict] = None):
        super().__init__(message)
        self.status = status
        self.payload = payload or {}


def is_configured() -> bool:
    """True when the proxy URL + internal token + brand are all set."""
    return bool(
        getattr(settings, "ZOHO_PROXY_URL", "")
        and getattr(settings, "ZOHO_PROXY_INTERNAL_TOKEN", "")
        and getattr(settings, "ZOHO_PROXY_BRAND", "")
    )


def proxy_call(
    service: str,
    action: str,
    *,
    method: str = "POST",
    resource_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Call /zoho/{service}/{action}[/{resource_id}] on the proxy and return the JSON body.

    Raises ZohoAPIError if the proxy / Zoho returns a non-2xx, or if the
    proxy is not configured. Callers should catch ZohoAPIError to map onto
    ZohoSyncLog status FAILED.
    """
    if not is_configured():
        raise ZohoAPIError(
            "Zoho proxy is not configured "
            "(set ZOHO_PROXY_URL + ZOHO_PROXY_INTERNAL_TOKEN + ZOHO_PROXY_BRAND)"
        )

    url = f"{settings.ZOHO_PROXY_URL.rstrip('/')}/zoho/{service}/{action}"
    if resource_id:
        url = f"{url}/{resource_id}"

    headers = {
        "X-Brand": settings.ZOHO_PROXY_BRAND,
        "X-Internal-Token": settings.ZOHO_PROXY_INTERNAL_TOKEN,
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"

    try:
        r = requests.request(
            method, url, headers=headers, json=payload, params=params, timeout=timeout
        )
    except requests.RequestException as exc:
        raise ZohoAPIError(f"Zoho proxy unreachable: {exc}") from exc

    if r.status_code >= 400:
        try:
            body = r.json()
        except ValueError:
            body = {"raw": r.text[:2000]}
        raise ZohoAPIError(
            f"Zoho proxy error: {r.status_code}",
            status=r.status_code,
            payload=body,
        )

    if not r.content:
        return {}
    try:
        return r.json()
    except ValueError:
        return {"raw": r.text}


def create_inventory_sales_order_payload(claim) -> Dict[str, Any]:
    """Build a Zoho Inventory sales order body for a claim.

    The proxy fills in organization_id from zoho_orgs based on X-Brand;
    we only send the per-order fields.
    """
    customer = claim.customer_account
    line = {
        "sku": claim.product.sku,
        "name": claim.product.description or claim.product.sku,
        "quantity": claim.quantity_affected or 1,
        "rate": float(claim.product.unit_cost or 0),
    }
    return {
        "customer_id": customer.zoho_account_id or "",
        "reference_number": claim.public_id,
        "line_items": [line],
        "custom_fields": [
            {"label": "Order Type", "value": "Warranty / Replacement"},
        ],
        "notes": f"Replacement for claim {claim.public_id} — ticket {claim.ticket.public_id}",
    }
