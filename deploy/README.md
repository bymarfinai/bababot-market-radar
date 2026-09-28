# core-prod VPS deployment

This deployment pack is intended for the BabaBot production VPS.

## Layout

The repository is expected at:

```text
/opt/core-app/app
```

Persistent host paths:

```text
/opt/core-app/data
/opt/core-app/backups
```

Docker Compose runs three services:

- `app`: BabaBot scanner/API/workers
- `db`: PostgreSQL 16
- `caddy`: reverse proxy and automatic HTTPS once `API_DOMAIN` is a real DNS name

PostgreSQL is intentionally not published to the host.

## First safe boot

From `/opt/core-app/app`:

```bash
cp .env.example .env
chmod 600 .env
```

Replace the two `CHANGE_ME` values before starting. Keep these disabled during migration validation:

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
curl -fsS http://127.0.0.1/health
```

With `API_DOMAIN=:80`, Caddy serves HTTP on port 80 for migration validation. Before switching the Vercel dashboard, point a DNS name to the VPS, set `API_DOMAIN` to that hostname, and restart Caddy so it can provision HTTPS.

## Safety

Do not publish port 5432. Do not enable live trading during database migration or parallel validation. Restore the existing production database before enabling paper/AI workers if preserving production state is required.
