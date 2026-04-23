from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "telegram_chat_id", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Nexus", {"fields": ("role", "phone", "avatar_url", "preferences", "telegram_chat_id")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Nexus", {"fields": ("role", "phone")}),
    )
