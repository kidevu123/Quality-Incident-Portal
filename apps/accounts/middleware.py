"""Request-scoped timezone activation (Eastern default; optional user preferences).

Set ``User.preferences["timezone"]`` to an IANA name (e.g. ``America/Chicago``) for
per-user display times in templates using ``localtime``.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone as dj_timezone


class ActivateUserTimezoneMiddleware:
    """Activate Django's timezone for template filters and ``localtime``."""

    def __init__(self, get_response):
        self.get_response = get_response
        try:
            self._default_tz = ZoneInfo(settings.TIME_ZONE)
        except ZoneInfoNotFoundError:
            self._default_tz = ZoneInfo("America/New_York")

    def __call__(self, request):
        tz = self._default_tz
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            prefs = getattr(user, "preferences", None) or {}
            if isinstance(prefs, dict):
                raw = prefs.get("timezone")
                if isinstance(raw, str) and raw.strip():
                    try:
                        tz = ZoneInfo(raw.strip())
                    except ZoneInfoNotFoundError:
                        pass
        dj_timezone.activate(tz)
        try:
            return self.get_response(request)
        finally:
            dj_timezone.deactivate()
