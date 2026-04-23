# Telegram notifications (Nexus Resolve)

New distributor claims (`/portal/claims/new/`) can trigger Telegram messages.

## Who receives claim alerts?

1. **Every chat ID** listed in `TELEGRAM_CHAT_IDS` (comma-separated). Use this for a **group/supergroup**, or your **personal numeric ID**, so you (the owner) always get every claim without linking in the UI.
2. **Plus** every **active** user who is a **superuser** or has role **Support Agent**, **Quality Manager**, or **Administrator** and has linked Telegram on **`/accounts/telegram/`** (their personal `telegram_chat_id`).

**Distributors** do **not** get new-claim pings from this path. **Finance** does not get automatic new-claim pings either; add them via `TELEGRAM_CHAT_IDS` if they should see every submission.

### “Someone is on it” (eye emoji)

In the **staff ticket workspace**, if a teammate sends a reply or internal note that contains **👁** or **👀**, Nexus also: adds an **internal note** (“X has accepted this claim/ticket…”), moves **New → Open** (if applicable), sets **assignee** when empty, and sends a Telegram HTML alert to **`TELEGRAM_CHAT_IDS`** plus every linked **Support Agent**, **Quality Manager**, **Administrator**, **Finance**, and **superuser** — except the sender’s own linked chat. The **Telegram message** and **auto internal note** are limited to about once per **10 minutes** per person per ticket (spam guard); **status/assignee** updates still apply when you post with the emoji.

**In Telegram:** the same workflow runs when a **linked** staff user (same roles as above; not distributors) either **reacts with 👁 or 👀** on the bot’s claim/ticket alert message, **replies** with those emojis to that alert, or sends a message that includes **TKT-…** or **CLM-…** (e.g. `👀 TKT-abc-123`). Reactions on a message that is not a mapped Nexus alert are ignored (no spam). The webhook must include **`message_reaction`** in `allowed_updates`, and you must **call `setWebhook` again** after changing it (see below). Telegram only delivers reaction updates if the bot can see reactions in that chat (in **groups**, the bot usually needs to be an **administrator**; **private** bot chats are fine).

Outbound claim/working-on messages register their `message_id` in cache so **replies and reactions** on that message resolve the ticket. Alerts sent **before** that code was deployed cannot be bound until a new alert is sent for that ticket.

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

Then register the webhook. **`allowed_updates` must include `message_reaction`** or 👀 reactions on alerts will never reach Nexus (typing commands in the bot chat does not change this).

**Preferred (uses `.env`):** set `TELEGRAM_WEBHOOK_URL=https://<your-domain>/portal/telegram/webhook/` and run on the server:

```bash
docker compose exec web python manage.py telegram_set_webhook
```

**Or curl** (replace placeholders):

```bash
curl -sS -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://<your-domain>/portal/telegram/webhook/",
    "secret_token": "<TELEGRAM_WEBHOOK_SECRET>",
    "allowed_updates": ["message", "edited_message", "message_reaction"]
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
