# core-prod VPS deployment

This deployment pack is the reproducible production layout for BabaBot Market Radar.

## Current production topology

The active Market Radar runtime is on the `core-prod` VPS:

- API: `https://core-prod.43-153-193-103.sslip.io`
- Dashboard: `https://radar.43-153-193-103.sslip.io`
- PostgreSQL: Docker-private only, never published on port 5432
- Paper trading: enabled in the production runtime
- AI approval: enabled in the production runtime
- Live trading: disabled unless explicitly armed later

Railway Market Radar services are retained only as a stopped rollback target. They are not part of the active production data path.
Their GitHub sources are intentionally disconnected so pushes to `main` cannot auto-start Railway. Reconnect the repository source explicitly before any rollback redeploy.

## Layout

Repository:

```text
/opt/core-app/app
```

Persistent host paths:

```text
/opt/core-app/data
/opt/core-app/backups
```

Docker Compose services:

- `app`: scanner, read API, AI approval workers, lifecycle, paper/live engines
- `db`: PostgreSQL 18
- `caddy`: HTTPS reverse proxy and static dashboard server

The dashboard files are mounted read-only into Caddy from `./dashboard`.

## First safe boot

From `/opt/core-app/app`:

```bash
cp .env.example .env
chmod 600 .env
```

Replace every `CHANGE_ME` value. Keep these disabled for a fresh migration or restore:

```text
PAPER_TRADING_ENABLED=false
AI_APPROVAL_ENABLED=false
LIVE_TRADING_ENABLED=false
```

Then:

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
```

Verify:

```bash
curl -fsS https://core-prod.43-153-193-103.sslip.io/health
curl -fsS -o /dev/null -w '%{http_code}\n' https://radar.43-153-193-103.sslip.io/
```

## PostgreSQL restore

Create a backup before a destructive database operation:

```bash
docker compose exec -T db pg_dump \
  --username=bababot \
  --dbname=bababot \
  --format=custom \
  --no-owner \
  --no-acl > /opt/core-app/backups/manual.dump
```

Restore only while the application writer is stopped:

```bash
docker compose stop app
docker compose exec -T db pg_restore \
  --username=bababot \
  --dbname=bababot \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  --exit-on-error < /opt/core-app/backups/manual.dump
docker compose up -d app
```

## Operations scripts

Tracked scripts:

- `deploy/bababot-backup.sh`: daily PostgreSQL custom-format backup, checksum, 7-day automatic retention
- `deploy/bababot-health.sh`: local Docker/app health watchdog; it does not call an AI provider
- `deploy/install-ops.sh`: installs the scripts into `~/.local/bin` and creates cron entries

Install/update them after a deploy:

```bash
cd /opt/core-app/app
chmod +x deploy/*.sh
./deploy/install-ops.sh
```

Expected cron entries:

```text
17 2 * * * $HOME/.local/bin/bababot-backup.sh >> $HOME/.local/state/bababot-backup.log 2>&1
*/5 * * * * $HOME/.local/bin/bababot-health.sh
```

A separate `@reboot` entry starts Desktop Commander on `core-prod`; it is operational access and not required by BabaBot itself.

## Runtime validation

Useful checks:

```bash
docker compose ps
docker stats --no-stream
df -h /
curl -fsS https://core-prod.43-153-193-103.sslip.io/health
curl -fsS https://core-prod.43-153-193-103.sslip.io/control/state
curl -fsS https://core-prod.43-153-193-103.sslip.io/paper/summary
```

The expected safe production state during paper validation is:

```text
AI_APPROVAL_ENABLED=true
PAPER_TRADING_ENABLED=true
LIVE_TRADING_ENABLED=false
live_armed=false
```

## Dashboard/API hostname

The current static dashboard points to:

```text
https://core-prod.43-153-193-103.sslip.io
```

If the production API hostname changes, update `dashboard/index.html` and `API_DOMAIN` together before deployment.

## Safety

- Never commit `.env` or any `.env.*` runtime copy.
- Never commit database dumps.
- Never expose PostgreSQL port 5432 publicly.
- Never enable or arm live trading as part of a deployment or database migration.
- Stop the application writer before restoring PostgreSQL.
- Preserve at least one verified off-service backup before destructive infrastructure changes.
