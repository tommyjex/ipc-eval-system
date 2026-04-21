#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$ROOT_DIR/logs"
RUN_DIR="$ROOT_DIR/run"

BACKEND_PORT="${BACKEND_PORT:-3001}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"

BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_LOG_FILE="$LOG_DIR/backend.log"
FRONTEND_LOG_FILE="$LOG_DIR/frontend.log"

mkdir -p "$LOG_DIR" "$RUN_DIR"

is_running() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi
  return 1
}

start_backend() {
  if is_running "$BACKEND_PID_FILE"; then
    echo "Backend is already running. PID=$(cat "$BACKEND_PID_FILE")"
    return
  fi

  if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
    echo "Missing backend virtualenv: $BACKEND_DIR/.venv"
    exit 1
  fi

  echo "Starting backend on port $BACKEND_PORT..."
  nohup bash -lc "
    cd '$BACKEND_DIR'
    export PORT='$BACKEND_PORT'
    source .venv/bin/activate
    exec python run.py
  " >>"$BACKEND_LOG_FILE" 2>&1 &
  echo $! >"$BACKEND_PID_FILE"
  echo "Backend started. PID=$(cat "$BACKEND_PID_FILE") log=$BACKEND_LOG_FILE"
}

build_frontend() {
  if [[ ! -d "$ROOT_DIR/node_modules" && ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "Missing frontend dependencies. Run: npm install"
    exit 1
  fi

  echo "Building frontend..."
  (
    cd "$ROOT_DIR"
    npm run build --workspace=frontend
  )
}

start_frontend() {
  if is_running "$FRONTEND_PID_FILE"; then
    echo "Frontend is already running. PID=$(cat "$FRONTEND_PID_FILE")"
    return
  fi

  build_frontend

  echo "Starting frontend preview on port $FRONTEND_PORT..."
  nohup bash -lc "
    cd '$FRONTEND_DIR'
    exec npm run preview -- --host 0.0.0.0 --port '$FRONTEND_PORT'
  " >>"$FRONTEND_LOG_FILE" 2>&1 &
  echo $! >"$FRONTEND_PID_FILE"
  echo "Frontend started. PID=$(cat "$FRONTEND_PID_FILE") log=$FRONTEND_LOG_FILE"
}

stop_service() {
  local name="$1"
  local pid_file="$2"
  if is_running "$pid_file"; then
    local pid
    pid="$(cat "$pid_file")"
    echo "Stopping $name. PID=$pid"
    kill "$pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  else
    echo "$name is not running."
    rm -f "$pid_file"
  fi
}

status_service() {
  local name="$1"
  local pid_file="$2"
  if is_running "$pid_file"; then
    echo "$name: running (PID=$(cat "$pid_file"))"
  else
    echo "$name: stopped"
  fi
}

start_all() {
  start_backend
  start_frontend
}

stop_all() {
  stop_service "frontend" "$FRONTEND_PID_FILE"
  stop_service "backend" "$BACKEND_PID_FILE"
}

status_all() {
  status_service "backend" "$BACKEND_PID_FILE"
  status_service "frontend" "$FRONTEND_PID_FILE"
  echo "Backend log:  $BACKEND_LOG_FILE"
  echo "Frontend log: $FRONTEND_LOG_FILE"
}

case "${1:-start}" in
  start)
    start_all
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    start_all
    ;;
  status)
    status_all
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
