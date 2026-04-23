from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from apps.accounts.views import NexusLoginView, NoWorkspaceAccessView
from apps.portal.telegram_pages import TelegramSettingsView, TelegramUnlinkView

urlpatterns = [
    path("health/", include("apps.core_health.urls")),
    path("admin/", admin.site.urls),
    path("accounts/login/", NexusLoginView.as_view(), name="login"),
    path(
        "accounts/no-workspace/",
        NoWorkspaceAccessView.as_view(),
        name="no_workspace_access",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/telegram/", TelegramSettingsView.as_view(), name="account_telegram"),
    path("accounts/telegram/unlink/", TelegramUnlinkView.as_view(), name="account_telegram_unlink"),
    path("portal/", include("apps.portal.urls")),
    path("api/", include("apps.api.urls")),
    path("", include("apps.support.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
