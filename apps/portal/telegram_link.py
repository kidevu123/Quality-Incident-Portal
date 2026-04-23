"""Short-lived tokens for Telegram deep-link binding (stored in Django cache)."""

from __future__ import annotations

import secrets

from django.core.cache import cache

_PREFIX = "nxlink_"
_CACHE_KEY = "telegram_link:v1:{}"
_TTL_SECONDS = 15 * 60


def mint_telegram_link_token(user_id: int) -> str:
    """Return a token to pass as ?start=… to t.me/<bot>. Expires in 15 minutes."""
    raw = secrets.token_urlsafe(16).replace("-", "").replace("_", "")[:20]
    token = f"{_PREFIX}{raw}"
    cache.set(_CACHE_KEY.format(token), user_id, timeout=_TTL_SECONDS)
    return token


def consume_telegram_link_token(token: str) -> int | None:
    """Validate one-time token and return user pk, or None."""
    if not token or not token.startswith(_PREFIX):
        return None
    key = _CACHE_KEY.format(token.strip())
    uid = cache.get(key)
    if uid is None:
        return None
    cache.delete(key)
    return int(uid)
