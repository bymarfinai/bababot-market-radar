#!/bin/bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/core-app/app}"
BACKUP_DIR="${BACKUP_DIR:-/opt/core-app/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
FINAL="$BACKUP_DIR/auto-bababot-$STAMP.dump"
TMP="$FINAL.tmp"

mkdir -p "$BACKUP_DIR"
cd "$APP_DIR"

DB_HEALTH="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' app-db-1 2>/dev/null || true)"
if [ "$DB_HEALTH" != "healthy" ]; then
  echo "$(date -Is) backup skipped: db health=$DB_HEALTH" >&2
  exit 1
fi

docker compose exec -T db sh -lc \
  'exec pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=custom --no-owner --no-acl' \
  > "$TMP"

test -s "$TMP"
chmod 600 "$TMP"
mv "$TMP" "$FINAL"

sha256sum "$FINAL" > "$FINAL.sha256"
chmod 600 "$FINAL.sha256"

# Keep seven days of automatic backups.
find "$BACKUP_DIR" -maxdepth 1 -type f \
  \( -name 'auto-bababot-*.dump' -o -name 'auto-bababot-*.dump.sha256' \) \
  -mtime +7 -delete

echo "$(date -Is) backup_ok $(basename "$FINAL") $(stat -c %s "$FINAL") bytes"
