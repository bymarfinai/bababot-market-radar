#!/bin/bash
set -u

APP_DIR="${APP_DIR:-/opt/core-app/app}"
STATE_DIR="${STATE_DIR:-$HOME/.local/state}"
LOG="$STATE_DIR/bababot-health.log"

mkdir -p "$STATE_DIR"
cd "$APP_DIR" || exit 1

ts="$(date -Is)"
app="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' app-app-1 2>/dev/null || echo missing)"
db="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' app-db-1 2>/dev/null || echo missing)"
caddy="$(docker inspect -f '{{.State.Status}}' app-caddy-1 2>/dev/null || echo missing)"

if [ "$app" = "unhealthy" ] || [ "$app" = "exited" ] || [ "$app" = "missing" ]; then
  echo "$ts app=$app action=start" >> "$LOG"
  docker compose up -d app >> "$LOG" 2>&1
else
  echo "$ts app=$app db=$db caddy=$caddy" >> "$LOG"
fi

if [ "$caddy" = "exited" ] || [ "$caddy" = "missing" ]; then
  echo "$ts caddy=$caddy action=start" >> "$LOG"
  docker compose up -d caddy >> "$LOG" 2>&1
fi

# Verify the app from inside its container. This never calls an AI provider.
docker compose exec -T app python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=5).read()" \
  >/dev/null 2>&1 || echo "$ts api_health_check=failed" >> "$LOG"

tail -n 500 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"
