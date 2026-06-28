#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/service-zyx"
cd "$APP_DIR"

echo "[deploy] git pull..."
git pull origin main

echo "[deploy] install dependencies..."
pip3 install -r requirements.txt -q

echo "[deploy] database setup..."
python3 scripts/setup.py

echo "[deploy] restart service..."
systemctl restart service-zyx
systemctl status service-zyx --no-pager

echo "[deploy] done."
