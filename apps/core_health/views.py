from django.db import connection
from django.http import JsonResponse


def health_live(_request):
    """Liveness — process up (no database)."""
    return JsonResponse({"status": "ok", "check": "live"})


def health_ready(_request):
    """Readiness — database reachable."""
    try:
        connection.ensure_connection()
    except Exception:  # noqa: BLE001
        return JsonResponse({"status": "unready", "check": "database"}, status=503)
    return JsonResponse({"status": "ok", "check": "ready"})
