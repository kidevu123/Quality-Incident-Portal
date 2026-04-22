# Nexus Resolve

Production-oriented **B2B distributor support platform**: Zendesk-style agent workspace, distributor portal, claims/RMA/reimbursement workflows, quality incidents, batch traceability hooks, rule-based automation, executive dashboards, audit logging, and a **first-class Zoho** integration layer (OAuth refresh, replacement sales order push with approval gates, dedupe, sync logs, Celery retries).

## Stack

- Django 4.2 LTS (Python 3.9+; Docker image uses 3.12)
- Django REST Framework
- PostgreSQL (SQLite optional for local dev via `USE_SQLITE=1`)
- Redis + Celery
- Nginx (reverse proxy + media)
- Tailwind (CDN in templates; swap to a built CSS bundle for strict CSP in production)
- WhiteNoise for static assets

## Quick start (local)

```bash
cd nexus-support
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export DJANGO_SETTINGS_MODULE=config.settings.development
export DJANGO_DEBUG=True
export USE_SQLITE=1
python manage.py migrate
python manage.py seed_nexus
python manage.py runserver
```

- Agent console: http://127.0.0.1:8000/ — `agent` / `agent123`
- Admin: http://127.0.0.1:8000/admin/ — `admin` / `admin123`
- Distributor portal: http://127.0.0.1:8000/portal/ — `distributor` / `dist123`
- API: http://127.0.0.1:8000/api/tickets/ (session auth)

## Docker Compose

```bash
cp .env.example .env
# Set DJANGO_SECRET_KEY and optionally Zoho vars
docker compose up --build
```

Application (via Nginx): http://localhost:8080/

Run migrations and create superuser inside `web` if needed:

```bash
docker compose exec web python manage.py createsuperuser
```

## Zoho configuration

Set in `.env`:

- `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`
- `ZOHO_ORG_ID` (Inventory organization id)
- `ZOHO_API_BASE` (e.g. `https://www.zohoapis.com` or EU/IN DC)

Without credentials, **replacement SO** uses a **simulated** success path so product flows can be demonstrated safely.

Tune `ZOHO_REPLACEMENT_SO_THRESHOLD` for finance approval before SO generation.

Extend `apps/zoho_integration/client.py` for CRM/Books-specific payloads (credit memos, invoice linkage).

## Proxmox layout (recommended)

| VM / LXC | Role |
|----------|------|
| `nexus-fe` | Nginx (TLS termination), optional WAF |
| `nexus-app` | Docker host: `web`, `worker`, `beat` |
| `nexus-data` | Managed PostgreSQL or dedicated `db` container with volume on ZFS |
| `nexus-cache` | Redis (persistent AOF if you treat queue as critical) |
| `nexus-backup` | Scheduled `pg_dump`, media snapshot, off-site sync |

Co-locate app and DB in the same site/VLAN; enforce firewall between tiers. Use **ZFS** or **Ceph** for DB volumes; snapshot before upgrades.

## Backup & restore

**PostgreSQL**

```bash
docker compose exec db pg_dump -U nexus nexus > backup.sql
cat backup.sql | docker compose exec -T db psql -U nexus nexus
```

**Media**

Archive the Docker volume `media_volume` or bind-mount to a ZFS dataset with snapshots.

## Project layout

- `apps/accounts` — custom `User`, roles
- `apps/crm` — accounts, products, batches, sales orders
- `apps/support` — tickets, messages, queues, macros
- `apps/claims` — claims, RMA, attachments, reimbursement, approvals
- `apps/quality` — incidents, investigations, CAPA
- `apps/zoho_integration` — client, services, sync logs, dedupe, Celery tasks
- `apps/automation` — JSON rules + engine
- `apps/auditlog` — audit entries + request middleware
- `apps/portal` — distributor UI
- `apps/api` — DRF API

## Production notes

- Set `DJANGO_DEBUG=false`, strong `DJANGO_SECRET_KEY`, real `DATABASE_URL`.
- Enable `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` when serving HTTPS.
- Set `BEHIND_TLS_PROXY=true` when TLS terminates at Nginx.
- Replace Tailwind CDN with a compiled stylesheet if CSP requires it.
- Add virus scanning and content-type validation for uploads; consider private object storage (S3-compatible) with signed URLs.

Further reading: `docs/WIREFRAMES.md`, `docs/SECURITY_CHECKLIST.md`, `docs/PHASE2_ROADMAP.md`.
