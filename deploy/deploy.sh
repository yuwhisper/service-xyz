#!/usr/bin/env bash
# 服务器本机手动部署（可选）。
# 推荐走 GitHub Actions：runner 打包后 SCP 上传（服务器访问 GitHub 常超时）。
set -euo pipefail

APP_DIR="/opt/service-zyx"
cd "$APP_DIR"

if [[ "${1:-}" == "--from-tarball" ]]; then
  TGZ="${2:-/tmp/service-zyx-release.tgz}"
  echo "[deploy] extract $TGZ ..."
  tar xzf "$TGZ" -C "$APP_DIR"
else
  echo "[deploy] fetch origin/main..."
  if ! git fetch origin main; then
    echo "[deploy] ERROR: git fetch failed (server cannot reach GitHub)."
    echo "[deploy] Use GitHub Actions deploy, or: bash deploy/deploy.sh --from-tarball /tmp/service-zyx-release.tgz"
    exit 1
  fi
  echo "[deploy] reset to origin/main..."
  git reset --hard origin/main
  git clean -fd -e .env -e ozon-fahuo-data -e '*.log' -e '__pycache__'
  echo "[deploy] HEAD=$(git rev-parse --short HEAD) $(git log -1 --pretty=%s)"
fi

echo "[deploy] install dependencies..."
pip3 install -r requirements.txt -q

echo "[deploy] database setup..."
python3 scripts/setup.py

echo "[deploy] restart service..."
systemctl restart service-zyx
systemctl is-active service-zyx
systemctl status service-zyx --no-pager | head -20

echo "[deploy] done."
