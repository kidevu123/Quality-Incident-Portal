# Deploy Nexus Resolve on Proxmox

This guide assumes a **single VM or LXC** running **Docker Engine** + **Docker Compose v2**, with the stack from this repository. The Compose file brings up **PostgreSQL**, **Redis**, **Django/Gunicorn**, **Celery worker**, **Celery beat**, and **Nginx**.

## Is it “finished”?

- **Deployment / operations**: The stack is intended to be **production-capable**: migrations on boot, static files via WhiteNoise, health checks, worker/beat separation, persistent volumes, and documented env vars.
- **Product scope**: This is a **full application foundation** (tickets, claims, portal, Zoho layer, automation hooks, dashboards). It is **not** a line-by-line clone of Zendesk; you should plan sprints for omnichannel adapters, advanced RBAC, and Zoho field mapping for *your* org.

---

## 1. Proxmox: create the guest

**Recommended (VM, Debian 12 or Ubuntu 22.04)**

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| vCPU | 2 | 4 |
| RAM | 4 GB | 8 GB |
| Disk | 40 GB SSD | 80 GB+ |
| Network | virtio, static DHCP or fixed IP | Same |

**LXC** works if nesting and Docker are supported; VMs are simpler for Docker storage drivers and kernel features.

Example: create a VM from the Proxmox UI, boot the ISO, install **Debian 12**, enable **SSH**, apply updates:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

---

## 2. Install Docker (official convenience script — or use distro packages)

**Option A — Docker’s install script (common on servers)**

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
# log out and back in so `docker` works without sudo
```

**Option B — Debian bookworm packages**

```bash
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Verify:

```bash
docker --version
docker compose version
```

---

## 3. Firewall (host)

Allow HTTP/HTTPS (adjust if you terminate TLS only on another layer):

```bash
sudo apt install -y ufw
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

---

## 4. Get the code and configure `.env`

```bash
sudo mkdir -p /opt/nexus-resolve
sudo chown "$USER:$USER" /opt/nexus-resolve
cd /opt/nexus-resolve
git clone https://github.com/kidevu123/Quality-Incident-Portal.git .
# or: git clone git@github.com:kidevu123/Quality-Incident-Portal.git .

cp .env.example .env
chmod 600 .env
nano .env   # or vim
```

**Required edits:**

1. **`DJANGO_SECRET_KEY`** — long random string:

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(50))"
   ```

2. **`DJANGO_ALLOWED_HOSTS`** — include the VM **hostname**, **IP**, and **public domain** (comma-separated, no spaces).

3. **`POSTGRES_PASSWORD`** and **`DATABASE_URL`** — use the **same** password. In `DATABASE_URL`, the host must be **`db`** (Docker service name). If the password contains `@`, `#`, etc., URL-encode it in `DATABASE_URL`.

4. When users access the site over **HTTPS**, set:

   - `SECURE_SSL_REDIRECT=true`
   - `SESSION_COOKIE_SECURE=true`
   - `CSRF_COOKIE_SECURE=true`
   - `BEHIND_TLS_PROXY=true` (if TLS terminates at Nginx/reverse proxy in front of this stack)
   - `CSRF_TRUSTED_ORIGINS=https://your.domain`

5. **Footer version** — comes from `config/version.py` in the code you deploy. If you ever added `NEXUS_APP_VERSION` to `.env`, remove it (it is no longer read; a stale value could make the footer look out of date). For an optional CI-only stamp, use `NEXUS_APP_VERSION_OVERRIDE`.

---

## 5. Build and start

**Automated (on the server as `root`)** — installs Docker if needed, clones the repo, writes `.env`, starts Compose:

```bash
apt-get update && apt-get install -y git
cd /opt && git clone https://github.com/kidevu123/Quality-Incident-Portal.git nexus-resolve
cd nexus-resolve && bash scripts/proxmox-node-deploy.sh
```

Optional: `NEXUS_EXTRA_ALLOWED_HOSTS=192.168.1.x,your.domain.com bash scripts/proxmox-node-deploy.sh`

**Manual:**

```bash
cd /opt/nexus-resolve
docker compose build --no-cache
docker compose up -d
docker compose ps
```

Logs:

```bash
docker compose logs -f web
docker compose logs -f worker
```

Health:

```bash
curl -sS http://127.0.0.1/health/live/
curl -sS http://127.0.0.1/health/ready/
```

By default Nginx publishes host port **80** (`NEXUS_HTTP_PORT`). Browse: `http://YOUR_VM_IP/`.

---

## 6. First-time Django setup

Create an admin user and (optional) seed demo data:

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_nexus
```

- Admin: `/admin/`
- Agent UI: `/`
- Portal: `/portal/`

---

## 7. TLS (recommended)

**Option A — TLS on a separate Proxmox VM (e.g. Caddy or Traefik)** that reverse-proxies to `http://nexus-vm:80` and sets `X-Forwarded-Proto: https`. Then set `BEHIND_TLS_PROXY=true` and secure cookie flags in `.env`, restart:

```bash
docker compose up -d
```

**Option B — Certbot on the same VM** (install Nginx + certbot on the host, not inside Docker) is possible but duplicates reverse proxy; prefer a dedicated edge proxy or add a `certbot` sidecar in Compose (advanced).

---

## 8. Backups

**PostgreSQL (nightly example)**

```bash
docker compose exec -T db pg_dump -U nexus nexus | gzip -c > "nexus-$(date +%F).sql.gz"
```

**Volumes** — include `postgres_data`, `redis_data`, `media_volume`, `celery_beat_data` in your Proxmox backup job (VM snapshot or `vzdump`).

**Restore DB**

```bash
gunzip -c nexus-YYYY-MM-DD.sql.gz | docker compose exec -T db psql -U nexus -d nexus
```

---

## 9. Upgrades

**Important:** After `pct enter` you land in `/root`. That is **not** the app — Git lives under **`/opt/nexus-resolve`**. If you see `fatal: not a git repository`, you are in the wrong directory.

**One command (recommended):**

```bash
bash /opt/nexus-resolve/scripts/server-upgrade.sh
```

**Manual (same steps):**

```bash
cd /opt/nexus-resolve
git pull
docker compose build
docker compose up -d
docker compose exec web python manage.py migrate --noinput
```

---

## 10. Troubleshooting

| Symptom | Check |
|--------|--------|
| `fatal: not a git repository` in the CT | You are in `~` (e.g. `/root`). Run `cd /opt/nexus-resolve` or `bash /opt/nexus-resolve/scripts/server-upgrade.sh`. |
| `web` unhealthy | `docker compose logs web` — often missing/invalid `DJANGO_SECRET_KEY` or DB URL |
| 502 from Nginx | `web` not healthy; `curl http://127.0.0.1:8000/health/live/` inside `web` container |
| CSRF errors | `CSRF_TRUSTED_ORIGINS` must match browser URL scheme + host |
| Celery not processing | `docker compose logs worker`; Redis reachable; `CELERY_BROKER_URL` overridden by Compose to `redis://redis:6379/0` |

---

## 11. Layout summary

```
[ Internet ]
     |
[ Proxmox VM: Nginx :80 ]  -->  gunicorn (web) :8000
                    \-->  /media volume
     [ postgres ] [ redis ] [ celery worker ] [ celery beat ]
```

All persistent state is in **named Docker volumes** — back them up or bind-mount to ZFS datasets if you prefer.
