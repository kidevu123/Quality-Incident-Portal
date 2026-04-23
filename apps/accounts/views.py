from urllib.parse import urlparse

from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.views.generic import TemplateView

from apps.accounts.models import Role
from apps.accounts.permissions import user_can_use_distributor_portal, user_has_role


class NexusLoginView(LoginView):
    """Send staff to the support inbox and distributors to the portal after login."""

    template_name = "registration/login.html"

    def get_success_url(self) -> str:
        user = self.request.user
        is_staff = user_has_role(user, Role.AGENT, Role.QUALITY, Role.FINANCE, Role.ADMIN)

        next_url = self.get_redirect_url()
        if next_url:
            path = urlparse(next_url).path or "/"
            if not path.startswith("/"):
                path = "/"
            # Do not send non-staff users to admin, API, or staff-only paths via ?next=
            if not is_staff and not (path == "/portal" or path.startswith("/portal/")):
                if user_can_use_distributor_portal(user):
                    return reverse("portal_home")
                return reverse("no_workspace_access")
            return next_url

        if is_staff:
            return reverse("support_inbox")
        if user_can_use_distributor_portal(user):
            return reverse("portal_home")
        return reverse("no_workspace_access")


class NoWorkspaceAccessView(TemplateView):
    """Break redirect loops for accounts with no staff or distributor workspace."""

    template_name = "accounts/no_workspace_access.html"
