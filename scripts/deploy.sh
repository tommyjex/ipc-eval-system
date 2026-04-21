#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="/root/ipc-eval-system"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
WEB_ROOT="/var/www/ipc-eval-system"
SERVICE_NAME="ipc-eval-backend"

INSTALL_BACKEND_DEPS="${INSTALL_BACKEND_DEPS:-1}"
INSTALL_FRONTEND_DEPS="${INSTALL_FRONTEND_DEPS:-1}"

echo "==> Deploy root: $ROOT_DIR"

if [[ ! -d "$ROOT_DIR" ]]; then
  echo "Project directory does not exist: $ROOT_DIR"
  exit 1
fi

if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
  echo "Backend virtualenv does not exist: $BACKEND_DIR/.venv"
  exit 1
fi

echo "==> Updating backend dependencies"
if [[ "$INSTALL_BACKEND_DEPS" == "1" ]]; then
  (
    cd "$BACKEND_DIR"
    source .venv/bin/activate
    pip install -r requirements.txt
  )
else
  echo "Skip backend dependency installation"
fi

echo "==> Updating frontend dependencies"
if [[ "$INSTALL_FRONTEND_DEPS" == "1" ]]; then
  (
    cd "$ROOT_DIR"
    npm install
  )
else
  echo "Skip frontend dependency installation"
fi

echo "==> Building frontend"
(
  cd "$ROOT_DIR"
  npm run build --workspace=frontend
)

echo "==> Sync frontend dist to $WEB_ROOT"
sudo mkdir -p "$WEB_ROOT"
sudo rm -rf "$WEB_ROOT"/*
sudo cp -r "$FRONTEND_DIR/dist/"* "$WEB_ROOT"/
sudo chown -R www-data:www-data "$WEB_ROOT"
sudo chmod -R 755 "$WEB_ROOT"

echo "==> Checking nginx configuration"
sudo nginx -t

echo "==> Restarting backend service"
sudo systemctl restart "$SERVICE_NAME"

echo "==> Reloading nginx"
sudo systemctl reload nginx

echo "==> Checking backend service status"
sudo systemctl --no-pager --full status "$SERVICE_NAME" || true

echo "==> Health check"
curl --fail --silent --show-error http://127.0.0.1:3001/api/health || true

echo "==> Deploy completed"
