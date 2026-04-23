"""Portal app models (org-wide settings editable from staff UI)."""

from django.db import models


class TelegramTeamInboxSettings(models.Model):
    """
    Singleton row (pk=1): extra team/supergroup chat IDs for claim and “on it” alerts.
    Supplements TELEGRAM_CHAT_IDS from the environment so admins can configure without server access.
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    team_chat_ids = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "Telegram team inbox (portal)"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "TelegramTeamInboxSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
