"""Register Telegram webhook URL + allowed_updates (incl. message_reaction)."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Call Telegram setWebhook so the bot receives messages and message_reaction updates. "
        "Set TELEGRAM_WEBHOOK_URL in .env to the full HTTPS URL "
        "(e.g. https://your.domain/portal/telegram/webhook/)."
    )

    def handle(self, *args, **options):
        token = (getattr(settings, "TELEGRAM_BOT_TOKEN", None) or "").strip()
        if not token:
            self.stderr.write("TELEGRAM_BOT_TOKEN is empty — nothing to do.")
            return

        hook = (getattr(settings, "TELEGRAM_WEBHOOK_URL", None) or "").strip()
        if not hook:
            self.stderr.write(
                "Set TELEGRAM_WEBHOOK_URL in .env to your public webhook URL "
                "(must match how Telegram reaches Django, ending with /portal/telegram/webhook/)."
            )
            return

        secret = (getattr(settings, "TELEGRAM_WEBHOOK_SECRET", None) or "").strip()
        body: dict = {
            "url": hook,
            "allowed_updates": ["message", "edited_message", "message_reaction"],
        }
        if secret:
            body["secret_token"] = secret

        api = f"https://api.telegram.org/bot{token}/setWebhook"
        req = urllib.request.Request(
            api,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            self.stderr.write(e.read().decode()[:2000])
            raise

        if not payload.get("ok"):
            self.stderr.write(str(payload))
            return

        self.stdout.write("setWebhook ok — verifying getWebhookInfo…")
        info_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
        with urllib.request.urlopen(info_url, context=ctx, timeout=15) as resp:
            info = json.loads(resp.read().decode())
        result = info.get("result") or {}
        self.stdout.write(f"url: {result.get('url')}")
        self.stdout.write(f"allowed_updates: {result.get('allowed_updates')}")
