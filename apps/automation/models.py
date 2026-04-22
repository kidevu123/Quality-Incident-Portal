from django.db import models


class AutomationRule(models.Model):
    name = models.CharField(max_length=128)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=100)
    conditions = models.JSONField(default=dict)
    actions = models.JSONField(default=dict)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "name"]

    def __str__(self) -> str:
        return self.name
