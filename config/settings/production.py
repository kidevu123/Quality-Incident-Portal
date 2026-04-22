from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import env  # noqa: F401

DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY or SECRET_KEY == "change-me-in-production-not-for-deploy" or len(SECRET_KEY) < 40:
    raise ImproperlyConfigured(
        "Production requires DJANGO_SECRET_KEY — set a long random string (40+ chars). "
        "Generate: python -c \"import secrets; print(secrets.token_urlsafe(50))\""
    )

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)

# If True, force non-secure cookies so sessions work over plain http:// (e.g. LAN IP to nginx).
# When SESSION_COOKIE_SECURE=True but you open http://192.168.x.x/, the browser will not store
# the session cookie and login appears to loop. Use HTTPS, or set this True for trusted LAN HTTP.
if env.bool("DJANGO_HTTP_SAFE_COOKIES", default=False):
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

if env.bool("BEHIND_TLS_PROXY", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS only when the site is actually served over HTTPS end-to-end (or TLS at proxy + secure cookies).
if SECURE_SSL_REDIRECT and SESSION_COOKIE_SECURE:
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=True)
else:
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Do not run the debug template context processor in production
TEMPLATES[0]["OPTIONS"]["context_processors"] = [  # type: ignore[name-defined]  # noqa: F405
    p
    for p in TEMPLATES[0]["OPTIONS"]["context_processors"]  # noqa: F405
    if p != "django.template.context_processors.debug"
]

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@localhost")
