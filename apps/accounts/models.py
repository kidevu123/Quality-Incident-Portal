from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    DISTRIBUTOR = "distributor", "Distributor"
    AGENT = "agent", "Support Agent"
    QUALITY = "quality", "Quality Manager"
    FINANCE = "finance", "Finance Approver"
    ADMIN = "admin", "Administrator"


class User(AbstractUser):
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.AGENT)
    phone = models.CharField(max_length=64, blank=True)
    avatar_url = models.URLField(blank=True)
    preferences = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["username"]

    def is_staff_role(self) -> bool:
        return self.role in {
            Role.AGENT,
            Role.QUALITY,
            Role.FINANCE,
            Role.ADMIN,
        }
