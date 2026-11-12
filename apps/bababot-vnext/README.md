# BabaBot vNext — Stage 02: VPS2 PAPER sync

The UI uses Next.js 16.4.6 and React 19.3.1 under `apps/bababot-vnext`.
It is **not** the production LIVE trading application.

## Architecture (NO VPS1)

```
VPS2 RESEARCH (5 read-only SQLite ledgers)
  exporter: export-strong-vps2.py
  publisher: publish-strong-vps2.mjs
     -- every 60s: check ledger diff (or heartbeat every 10min)
     -- outbound HTTPS, private @vercel/blob
          |
Vercel private Blob (SIN1): research/strong-paper/latest.json
          |
Next.js GET /api/strong (server-only Blob token)
          |
Browser UI (read-only polling every 60s while visible)
```

No incoming port required on VPS2. No VPS1 gateway, DNS, firewall or LIVE execution changes.
Private Blob credentials only exist in VPS2 local restricted env and Vercel server env.
Do not commit keys or trade snapshots in public GitHub.

## Source provenance
- Original A: `ip01-independent-paper/v2_a_independent_paper.sqlite3`.
- P01–P07: `strong-seven-modular-20261107/seven_forward.sqlite3`.
- M01–M02: `strong-master-matrix-20261108/master_forward.sqlite3`.
- M03: `strong-m03-modular-20261108/m03_forward.sqlite3`.
- M04–M05: `strong-m04-m05-modular-20261109/m45_forward.sqlite3`.

All DBs are opened `mode=ro` and `PRAGMA query_only=ON`.
PnL, fees and close reasons come from original ledger. Matching is on full
`sourceEventId`; sum metrics **per strategy**, not across overlapping branches.

## VPS2 publisher
Files to deploy on VPS2:
`scripts/export-strong-vps2.py`, `scripts/publish-strong-vps2.mjs`,
`deploy/bababot-paper-sync.service`, `deploy/bababot-paper-sync.timer`.

Install npm in an isolated `/home/ubuntu/bababot-strong-sync` directory and
add one secret file `/home/ubuntu/bababot-strong-sync/blob.env` with
`BLOB_READ_WRITE_TOKEN=...` (mode 0600). Install a separate systemd
oneshot service and timer (60-second interval). No order endpoint exists.

The publisher computes a normalized payload hash excluding generatedAt and
uploads on changes or when 10min have elapsed since last successful upload.
It persists the last uploaded hash in a private local state file; failures
are retried next timer execution. Private Blob overwrites use
`allowOverwrite=true`, `addRandomSuffix=false`.

## Vercel setup
Vercel project: `bababot-vnext-research` (protected).
Store: `bababot-vnext-paper-private`, private, SIN1.
The store connection injects server-only `BLOB_READ_WRITE_TOKEN`.
`GET /api/strong` always disables caching and checks actual snapshot timestamp;
data older than 20min shows a stale warning, never fake live status.

Optional signed read bridge via `STRONG_READ_API_URL` remains as a fallback,
but it is not needed with private Blob and should not route via VPS1.
Legacy `STRONG_PAPER_SNAPSHOT_JSON` remains as an explicit disaster fallback.

## Local validation
```bash
cd apps/bababot-vnext
npm ci
npm run typecheck
npm run build
npm audit --omit=dev
```
The Next.js route reads Blob dynamically. Without Blob credentials, it falls
back to preview env snapshot, with mode `snapshot` rather than `sync`.

## Safety
- No writes to PAPER ledgers.
- No VPS1 requests or operations.
- No auto orders, POST/PATCH/DELETE trading API or strategy changes.
- Do not interpret ACTIVE as live process heartbeat; it is research enrollment.
- No source data is invented; empty/invalid or stale snapshots are labeled.

## Stage 03 — Vela Chart / Futures PAPER Replay

- New **Vela Chart & Replay** tab (engine-free Vela Apache-2.0; no PineTS dependency).
- Binance **USDT-M perpetual Futures** Kline OHLCV, not Spot or invented candles.
- Real PAPER marker timestamps/prices come from VPS2 ledger, matched by original source event.
- Supports 1m/5m/15m/1h/4h, historical view, Vela drawing tools, causal one-bar-at-a-time replay.
- Chart read endpoint `GET /api/market/candles?tradeId=<ledger-trade-id>&timeframe=5m`, guarded by actual PAPER snapshot; private cache path per source event + timeframe, with Binance FAPI fallback.
- Missing candle sources return a visible error; no fake candles or simulated price fills.
- Vela attribution remains visible on chart and links to https://velacharts.dev, per Vela NOTICE.
- No PineTS compiler, no order calls or VPS1 dependencies.
