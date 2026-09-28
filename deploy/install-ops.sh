#!/bin/bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/core-app/app}"
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
STATE_DIR="${STATE_DIR:-$HOME/.local/state}"

mkdir -p "$BIN_DIR" "$STATE_DIR" /opt/core-app/backups

install -m 700 "$APP_DIR/deploy/bababot-backup.sh" "$BIN_DIR/bababot-backup.sh"
install -m 700 "$APP_DIR/deploy/bababot-health.sh" "$BIN_DIR/bababot-health.sh"

(
  crontab -l 2>/dev/null |
    grep -v 'bababot-backup.sh' |
    grep -v 'bababot-health.sh' || true
  echo '17 2 * * * $HOME/.local/bin/bababot-backup.sh >> $HOME/.local/state/bababot-backup.log 2>&1'
  echo '*/5 * * * * $HOME/.local/bin/bababot-health.sh'
) | crontab -

echo "BabaBot ops scripts installed."
crontab -l | grep -E 'bababot-(backup|health)\.sh'
