import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_safe

from apps.support.push import (
    deactivate_push_subscription,
    upsert_push_subscription,
    web_push_is_configured,
)


@require_safe
def service_worker(request):
    path = settings.BASE_DIR / "static" / "sw.js"
    return HttpResponse(path.read_text(), content_type="application/javascript")


@require_safe
def manifest(request):
    path = settings.BASE_DIR / "static" / "manifest.webmanifest"
    return HttpResponse(path.read_text(), content_type="application/manifest+json")


@login_required
@require_safe
def push_config(request):
    return JsonResponse(
        {
            "enabled": web_push_is_configured(),
            "publicKey": getattr(settings, "WEB_PUSH_VAPID_PUBLIC_KEY", ""),
        }
    )


@login_required
@require_POST
def push_subscribe(request):
    payload = json.loads(request.body.decode("utf-8") or "{}")
    upsert_push_subscription(
        request.user,
        payload,
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    return JsonResponse({"ok": True})


@login_required
@require_POST
def push_unsubscribe(request):
    payload = json.loads(request.body.decode("utf-8") or "{}")
    endpoint = (payload.get("endpoint") or "").strip()
    if endpoint:
        deactivate_push_subscription(endpoint, user=request.user)
    return JsonResponse({"ok": True})
