# Telegram notifications (Nexus Resolve)

New distributor claims (`/portal/claims/new/`) can trigger Telegram messages.

## Who receives claim alerts?

1. **Every chat ID** listed in `TELEGRAM_CHAT_IDS` (comma-separated). Use this for a **group/supergroup**, or your **personal numeric ID**, so you (the owner) always get every claim without linking in the UI.
2. **Plus** every **active** user who is a **superuser** or has role **Support Agent**, **Quality Manager**, or **Administrator** and has linked Telegram on **`/accounts/telegram/`** (their personal `telegram_chat_id`).

**Distributors** and **Finance** users do **not** get claim pings from this path (even if they somehow open the link). **Finance** is excluded; add them via `TELEGRAM_CHAT_IDS` if needed.

## 1. Create the bot

1. Open Telegram, search **@BotFather**, send `/newbot`, follow prompts.
2. Copy the **HTTP API token** → set `TELEGRAM_BOT_TOKEN` in `.env`.
3. Set **`TELEGRAM_BOT_USERNAME`** to the bot username **without** `@` (e.g. `NexusResolveBot`).

## 2. Redis cache (production)

Deep-link bind tokens are stored in Django’s cache. With multiple Gunicorn workers you **must** use Redis:

- Docker Compose already sets `REDIS_CACHE_URL=redis://redis:6379/2` for the `web` service.
- For other hosts, set `REDIS_CACHE_URL` to a Redis URL (e.g. database `2` so it does not clash with Celery `0`).

## 3. Register the webhook (HTTPS required)

Telegram must reach your **public HTTPS** URL:

`https://<your-domain>/portal/telegram/webhook/`

Generate a random secret (long random string) and set **`TELEGRAM_WEBHOOK_SECRET`** in `.env` to the same value.

Then call **setWebhook** (replace placeholders):

```bash
curl -sS -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://<your-domain>/portal/telegram/webhook/",
    "secret_token": "<TELEGRAM_WEBHOOK_SECRET>",
    "allowed_updates": ["message", "edited_message"]
  }'
```

Verify:

```bash
curl -sS "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo"
```

## 4. Bind your account (instant deep link)

1. Sign in to Nexus.
2. Open **`/accounts/telegram/`** (also linked from the portal nav as **Telegram** and from the support sidebar as **Telegram alerts**).
3. Click **Open Telegram and bind**, then tap **Start** in the bot chat.

If binding fails, check webhook info, HTTPS, and that `REDIS_CACHE_URL` is set for all web workers.

## 5. Owner: see all notifications

- Put your personal chat ID (or a team **supergroup** ID) in **`TELEGRAM_CHAT_IDS`** so every claim is copied there, **or**
- Use a **Support Agent**, **Quality Manager**, **Administrator**, or **superuser** account and link Telegram on `/accounts/telegram/`.

You can use **both** (group + linked admin) without duplicate suppression—duplicate chat IDs are deduplicated when sending.

## Environment reference

| Variable | Required | Purpose |
|----------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | For notifications + webhook replies | Bot API token |
| `TELEGRAM_BOT_USERNAME` | For deep links | Username without `@` |
| `TELEGRAM_CHAT_IDS` | Optional | Extra recipients (e.g. owner group) |
| `TELEGRAM_WEBHOOK_SECRET` | Strongly recommended | Validates `X-Telegram-Bot-Api-Secret-Token` |
| `REDIS_CACHE_URL` | Production | Bind tokens across workers |

After changing `.env`, recreate the `web` container:  
`docker compose up -d --force-recreate web`
