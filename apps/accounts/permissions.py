"""RBAC helpers — product roles."""

from .models import Role, User


def user_has_role(user: User, *roles: str) -> bool:
    if not user.is_authenticated:
        return False
    if user.role == Role.ADMIN or user.is_superuser:
        return True
    return user.role in roles
