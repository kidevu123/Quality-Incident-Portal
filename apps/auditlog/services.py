from typing import Any, Optional

from .middleware import get_current_request
from .models import AuditLog


def write_audit(
    *,
    actor,
    action: str,
    object_type: str = "",
    object_id: str = "",
    before: Optional[dict] = None,
    after: Optional[dict] = None,
) -> AuditLog:
    req = get_current_request()
    ip = user_agent = None
    if req:
        ip = req.META.get("REMOTE_ADDR")
        user_agent = (req.META.get("HTTP_USER_AGENT") or "")[:512]
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=str(object_id) if object_id else "",
        before=before or {},
        after=after or {},
        ip_address=ip,
        user_agent=user_agent,
    )


def snapshot_model(instance: Any) -> dict:
    if instance is None:
        return {}
    return {f.name: getattr(instance, f.name) for f in instance._meta.concrete_fields}
