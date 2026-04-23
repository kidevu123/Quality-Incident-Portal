"""RBAC helpers — product roles."""

from .models import Role, User


def user_has_role(user: User, *roles: str) -> bool:
    if not user.is_authenticated:
        return False
    if user.role == Role.ADMIN or user.is_superuser:
        return True
    return user.role in roles


def user_can_use_distributor_portal(user: User) -> bool:
    """True if this account may open /portal/ (distributor or admin)."""
    return user_has_role(user, Role.DISTRIBUTOR, Role.ADMIN)
