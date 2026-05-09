"""Browser Web Push delivery."""

from __future__ import annotations

import base64
import json
import logging

from django.conf import settings
from django.utils import timezone

from apps.support.models import Notification, PushSubscription

logger = logging.getLogger(__name__)


def web_push_is_configured() -> bool:
    return bool(
        getattr(settings, "WEB_PUSH_VAPID_PUBLIC_KEY", "")
        and getattr(settings, "WEB_PUSH_VAPID_PRIVATE_KEY_B64", "")
    )


def _private_key_pem() -> str:
    raw = getattr(settings, "WEB_PUSH_VAPID_PRIVATE_KEY_B64", "") or ""
    return base64.b64decode(raw).decode("utf-8")


def upsert_push_subscription(user, payload: dict, user_agent: str = "") -> PushSubscription:
    keys = payload.get("keys") or {}
    endpoint = (payload.get("endpoint") or "").strip()
    p256dh = (keys.get("p256dh") or "").strip()
    auth = (keys.get("auth") or "").strip()
    if not endpoint or not p256dh or not auth:
        raise ValueError("Push subscription is missing endpoint or keys.")
    sub, _ = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": user,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": user_agent[:1000],
            "is_active": True,
        },
    )
    return sub


def deactivate_push_subscription(endpoint: str, user=None) -> None:
    qs = PushSubscription.objects.filter(endpoint=endpoint)
    if user is not None:
        qs = qs.filter(user=user)
    qs.update(is_active=False)


def send_web_push_notification(notification: Notification) -> None:
    if not web_push_is_configured():
        return
    try:
        from pywebpush import WebPushException, webpush
    except Exception:  # noqa: BLE001
        logger.exception("pywebpush is not available")
        return

    payload = {
        "title": notification.title,
        "body": notification.body or "Ticket activity updated.",
        "url": notification.url or "/notifications/",
        "tag": f"ticket-{notification.ticket_id or notification.pk}",
        "timestamp": int(notification.created_at.timestamp() * 1000),
    }
    private_key = _private_key_pem()
    claims = {"sub": getattr(settings, "WEB_PUSH_VAPID_SUBJECT", "mailto:admin@nexus-resolve.local")}

    for sub in PushSubscription.objects.filter(user=notification.recipient, is_active=True):
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth,
            },
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=private_key,
                vapid_claims=claims,
                timeout=8,
            )
            sub.last_used_at = timezone.now()
            sub.save(update_fields=["last_used_at", "updated_at"])
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in {404, 410}:
                sub.is_active = False
                sub.save(update_fields=["is_active", "updated_at"])
            else:
                logger.warning("Web push failed for subscription %s: %s", sub.pk, exc)
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected web push failure for subscription %s", sub.pk)


def send_web_push_for_notifications(notifications: list[Notification]) -> None:
    for notification in notifications:
        send_web_push_notification(notification)
