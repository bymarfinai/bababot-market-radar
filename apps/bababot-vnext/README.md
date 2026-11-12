# BabaBot vNext — Stages 01 + 02

Next.js 15 / React 19 / TypeScript scaffold for STRONG LONG Independent PAPER.
This app is intentionally isolated from the legacy `dashboard/` static production
and from VPS1 trading controls. No trading/order POST endpoints exist here.

## Stage 01
- App Router scaffold under `apps/bababot-vnext/`.
- Responsive dark research terminal with Overview, Strategies, Matched Compare,
  Trade Explorer, and System Data views.
- Legacy terminal remains available via explicit external link, not overwritten.

## Stage 02
- Read-only Next.js endpoint `GET /api/strong`, schema v1.
- Python SQLite exporter at `scripts/export-strong-vps2.py`. Opens five
  independent VPS2 ledgers with SQLite `mode=ro` and `PRAGMA query_only=ON`.
- All P/M outcomes are grouped by `sourceEventId` (not symbol). No automatic
  portfolio PnL sum across strategies; shared candidate signals overlap.
- Server-only `STRONG_READ_API_URL` + `STRONG_READ_API_TOKEN` support an
  authenticated HTTPS read bridge when provisioned.
- Server-only `STRONG_PAPER_SNAPSHOT_JSON` is an explicit, timestamped fallback
  for preview deployments. Do not publish personal/strategy trade snapshots
  to the public repository.

## Run
```sh
cd apps/bababot-vnext
npm install
npm run typecheck
npm run build
npm run dev
```

## Export on VPS2 (read-only)
```sh
python3 scripts/export-strong-vps2.py --root /home/ubuntu/market-detektor-research > /tmp/strong-paper-snapshot.json
python3 -m json.tool /tmp/strong-paper-snapshot.json >/dev/null
```
Never put the exported JSON in Git. Set `STRONG_PAPER_SNAPSHOT_JSON`
as a **private server-side Vercel Preview environment variable** to render a
point-in-time real-ledger preview. Production and LIVE controls remain unchanged.

## Future live bridge
Provision an authenticated, HTTPS-only read service for the exported schema
in an isolated VPS2 process. Do not expose the SQLite files, source order-flow
tape, write endpoints, or public unauthenticated API. Next.js will consume the
bridge without changing the browser contract. The online bridge is not
considered ready until connectivity, auth, freshness and parity checks pass.

## Security/invariants
- No mutation of research SQLite ledgers; no DB writes in exporter.
- No shared LIVE trading API, no Binance orders.
- Exactly one `sourceEventId` per original qualification, one result per
  strategy and event.
- All times epoch ms UTC. PnL is realized net from source ledger; no invention.
- Snapshot status and freshness always visible.
- `STRONG_READ_API_TOKEN` never exposed to client JS.
