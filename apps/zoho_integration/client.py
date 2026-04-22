"""Zoho API client — OAuth refresh + Inventory / Books style endpoints."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ZohoAPIError(Exception):
    def __init__(self, message: str, status: Optional[int] = None, payload: Optional[Dict] = None):
        super().__init__(message)
        self.status = status
        self.payload = payload or {}


class ZohoClient:
    """Minimal client: token refresh + POST JSON. Extend per product (Inventory, Books, CRM)."""

    TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"

    def __init__(self):
        self._access_token: Optional[str] = None
        self._access_expires_at: float = 0

    def _refresh_access_token(self) -> str:
        cid = settings.ZOHO_CLIENT_ID
        secret = settings.ZOHO_CLIENT_SECRET
        refresh = settings.ZOHO_REFRESH_TOKEN
        if not all([cid, secret, refresh]):
            raise ZohoAPIError("Zoho OAuth credentials not configured")
        r = requests.post(
            self.TOKEN_URL,
            data={
                "refresh_token": refresh,
                "client_id": cid,
                "client_secret": secret,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        if r.status_code >= 400:
            raise ZohoAPIError("Token refresh failed", status=r.status_code, payload=r.json() if r.content else {})
        data = r.json()
        token = data.get("access_token")
        if not token:
            raise ZohoAPIError("No access_token in refresh response", payload=data)
        expires_in = int(data.get("expires_in_sec") or data.get("expires_in") or 3600)
        self._access_token = token
        self._access_expires_at = time.time() + expires_in - 60
        return token

    def access_token(self) -> str:
        if self._access_token and time.time() < self._access_expires_at:
            return self._access_token
        return self._refresh_access_token()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> Dict[str, Any]:
        base = settings.ZOHO_API_BASE.rstrip("/")
        url = f"{base}{path}"
        headers = {"Authorization": f"Zoho-oauthtoken {self.access_token()}"}
        r = requests.request(method, url, headers=headers, params=params, json=json, timeout=60)
        if r.status_code >= 400:
            try:
                payload = r.json()
            except Exception:  # noqa: BLE001
                payload = {"raw": r.text[:2000]}
            raise ZohoAPIError(f"Zoho API error: {r.status_code}", status=r.status_code, payload=payload)
        if not r.content:
            return {}
        return r.json()


def create_inventory_sales_order_payload(claim) -> Dict[str, Any]:
    """Build a Zoho Inventory–style sales order body (adapt fields to your org)."""
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
