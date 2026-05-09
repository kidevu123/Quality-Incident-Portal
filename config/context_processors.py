from django.conf import settings


def nexus_release(request):
    """Expose version string to all templates."""
    return {"nexus_app_version": getattr(settings, "NEXUS_APP_VERSION", "0.0.0")}


def notifications(request):
    """Expose lightweight notification state to navigation templates."""
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return {"unread_notification_count": 0}
    try:
        from apps.support.notifications import unread_notification_count

        count = unread_notification_count(user)
    except Exception:  # noqa: BLE001 - keep auth pages resilient during migrations
        count = 0
    return {"unread_notification_count": count}
