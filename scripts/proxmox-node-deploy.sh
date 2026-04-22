#!/usr/bin/env bash
# Run ON the Linux host (Proxmox node or VM/LXC) as root.
#
# On your Mac you already have: ssh root@192.168.1.190
# Copy this script to the server, or from repo:
#   cd /opt && git clone https://github.com/kidevu123/Quality-Incident-Portal.git nexus-resolve
#   bash nexus-resolve/scripts/proxmox-node-deploy.sh
#
# Optional env:
#   NEXUS_REPO_URL  NEXUS_INSTALL_DIR  NEXUS_HTTP_PORT  NEXUS_EXTRA_ALLOWED_HOSTS

set -euo pipefail

NEXUS_REPO_URL="${NEXUS_REPO_URL:-https://github.com/kidevu123/Quality-Incident-Portal.git}"
NEXUS_INSTALL_DIR="${NEXUS_INSTALL_DIR:-/opt/nexus-resolve}"
NEXUS_HTTP_PORT="${NEXUS_HTTP_PORT:-80}"

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

echo "NOTE: Prefer a dedicated VM/LXC for Docker; running on the Proxmox node is convenient but not ideal isolation." >&2

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-v2 git curl ca-certificates python3
systemctl enable --now docker

mkdir -p "$NEXUS_INSTALL_DIR"
cd "$NEXUS_INSTALL_DIR"

if [[ ! -d .git ]]; then
  git clone "$NEXUS_REPO_URL" .
else
  git pull --ff-only
fi

chmod +x scripts/entrypoint.sh 2>/dev/null || true

export DB_PASS="$(openssl rand -hex 24)"
export DJANGO_SECRET="$(openssl rand -base64 64 | tr -d '\n' | tr '+/' '-_' | cut -c1-64)"
HOST_FQDN="$(hostname -f 2>/dev/null || true)"
HOST_SHORT="$(hostname 2>/dev/null || echo localhost)"
ALLOWED="localhost,127.0.0.1,web,nginx,${HOST_SHORT}"
if [[ -n "${HOST_FQDN}" && "${HOST_FQDN}" != "${HOST_SHORT}" ]]; then
  ALLOWED="${ALLOWED},${HOST_FQDN}"
fi
if [[ -n "${NEXUS_EXTRA_ALLOWED_HOSTS:-}" ]]; then
  ALLOWED="${ALLOWED},${NEXUS_EXTRA_ALLOWED_HOSTS}"
fi
export ALLOWED
export NEXUS_HTTP_PORT

if [[ ! -f .env ]]; then
  cp .env.example .env
fi
chmod 600 .env

python3 - <<'PY'
import os
import re
from pathlib import Path

p = Path(".env")
t = p.read_text()
t = re.sub(r"^DJANGO_SECRET_KEY=.*$", "DJANGO_SECRET_KEY=" + os.environ["DJANGO_SECRET"], t, flags=re.M)
t = re.sub(r"^POSTGRES_PASSWORD=.*$", "POSTGRES_PASSWORD=" + os.environ["DB_PASS"], t, flags=re.M)
t = re.sub(
    r"^DATABASE_URL=.*$",
    "DATABASE_URL=postgres://nexus:" + os.environ["DB_PASS"] + "@db:5432/nexus",
    t,
    flags=re.M,
)
t = re.sub(r"^DJANGO_ALLOWED_HOSTS=.*$", "DJANGO_ALLOWED_HOSTS=" + os.environ["ALLOWED"], t, flags=re.M)
t = re.sub(r"^NEXUS_HTTP_PORT=.*$", "NEXUS_HTTP_PORT=" + os.environ["NEXUS_HTTP_PORT"], t, flags=re.M)
p.write_text(t)
PY

docker compose build --no-cache
docker compose up -d

echo ""
echo "=== Waiting for web (up to 90s) ==="
for _ in $(seq 1 18); do
  if curl -sf "http://127.0.0.1:${NEXUS_HTTP_PORT}/health/live/" >/dev/null; then
    echo "Live check OK"
    curl -sf "http://127.0.0.1:${NEXUS_HTTP_PORT}/health/ready/" && echo "Ready check OK" || true
    IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    echo ""
    echo "Open: http://${IP}:${NEXUS_HTTP_PORT}/"
    echo "Admin: http://${IP}:${NEXUS_HTTP_PORT}/admin/"
    echo ""
    echo "Create admin user:"
    echo "  cd ${NEXUS_INSTALL_DIR} && docker compose exec web python manage.py createsuperuser"
    exit 0
  fi
  sleep 5
done

echo "Health check timed out. Logs:" >&2
docker compose logs web --tail 80 >&2
exit 1
