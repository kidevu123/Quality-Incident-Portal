# Generated manually for portal app

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TelegramTeamInboxSettings",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("team_chat_ids", models.JSONField(blank=True, default=list)),
            ],
            options={
                "verbose_name": "Telegram team inbox (portal)",
            },
        ),
    ]
