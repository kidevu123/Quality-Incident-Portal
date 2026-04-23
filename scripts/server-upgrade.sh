#!/usr/bin/env bash
# Upgrade Nexus Resolve on the server (Proxmox CT/VM). Safe to run as root.
# Repo path is NOT your home directory — use /opt/nexus-resolve (see docs/DEPLOY_PROXMOX.md).
#
# From anywhere:
#   bash /opt/nexus-resolve/scripts/server-upgrade.sh
#
# Or:
#   NEXUS_INSTALL_DIR=/srv/other-path bash /srv/other-path/scripts/server-upgrade.sh

set -euo pipefail

NEXUS_INSTALL_DIR="${NEXUS_INSTALL_DIR:-/opt/nexus-resolve}"

if [[ ! -d "$NEXUS_INSTALL_DIR" ]]; then
  echo "ERROR: Install directory not found: $NEXUS_INSTALL_DIR" >&2
  echo "If you never cloned here, see docs/DEPLOY_PROXMOX.md — usually:" >&2
  echo "  cd /opt && git clone https://github.com/kidevu123/Quality-Incident-Portal.git nexus-resolve" >&2
  exit 1
fi

cd "$NEXUS_INSTALL_DIR"

if [[ ! -d .git ]]; then
  echo "ERROR: No git repo in $NEXUS_INSTALL_DIR (.git missing)." >&2
  echo "You may be in the wrong folder, or this was a copy without .git." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker and 'docker compose' are required." >&2
  exit 1
fi

echo "==> $NEXUS_INSTALL_DIR — pulling latest main"
git fetch origin
git pull --ff-only origin main

echo "==> Rebuilding and restarting stack"
docker compose build
docker compose up -d

echo "==> Migrations"
docker compose exec -T web python manage.py migrate --noinput

echo "==> Done. Footer should match config/version.py after refresh (check with: grep VERSION config/version.py)"
