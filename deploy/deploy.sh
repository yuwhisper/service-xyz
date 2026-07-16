#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/service-zyx"
cd "$APP_DIR"

echo "[deploy] fetch origin/main..."
git fetch origin main

echo "[deploy] reset to origin/main (discard local dirty tree)..."
# Keep runtime data / env; drop untracked junk that blocks clean checkout
git reset --hard origin/main
git clean -fd -e .env -e ozon-fahuo-data -e '*.log' -e '__pycache__'

echo "[deploy] HEAD=$(git rev-parse --short HEAD) $(git log -1 --pretty=%s)"

echo "[deploy] install dependencies..."
pip3 install -r requirements.txt -q

echo "[deploy] database setup..."
python3 scripts/setup.py

echo "[deploy] restart service..."
systemctl restart service-zyx
systemctl is-active service-zyx
systemctl status service-zyx --no-pager | head -20

echo "[deploy] done."
