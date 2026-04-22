from django.conf import settings


def nexus_release(request):
    """Expose version string to all templates."""
    return {"nexus_app_version": getattr(settings, "NEXUS_APP_VERSION", "0.0.0")}
