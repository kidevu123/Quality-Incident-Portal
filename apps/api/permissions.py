from rest_framework.permissions import BasePermission

from apps.accounts.models import Role
from apps.accounts.permissions import user_has_role


class IsStaffRole(BasePermission):
    def has_permission(self, request, view):
        return user_has_role(
            request.user,
            Role.AGENT,
            Role.QUALITY,
            Role.FINANCE,
            Role.ADMIN,
        )
