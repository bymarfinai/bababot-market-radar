# LQ-UI1 — Causal Liquidity Zones on Existing Chart

Status: **IMPLEMENTED**

## Scope

LQ-UI1 adds the frozen LQ-1 structural supply/demand model to the existing dashboard chart without changing trading authority.

Implemented:

- 5m / 15m / 1h causal supply and demand overlays
- FRESH / TESTED state labels
- departure ATR and touch count in the location panel
- nearest supply / nearest demand summary
- LQ-2 research tag:
  - `AVOID CANDIDATE` when the reference price is inside FRESH 15m supply
  - `OPEN LANE CANDIDATE` otherwise
- LIVE map mode
- ENTRY SNAPSHOT mode from Position History
- clicking a closed position loads its symbol and entry-time causal map
- historical chart window includes candles after entry for visual rejection / breakout / acceptance audit while keeping the zones frozen at entry time
- LQ Zones visibility toggle
- Live button resets the chart back to current market context

## API

New read-only endpoint:

`GET /market/liquidity-zones?symbol=...&asof_ms=...&reference_price=...`

The endpoint uses the same LQ-1 causal contract:

- zone birth only after two right-side confirmation bars are closed
- minimum departure = 0.75 ATR
- active original-role zones are FRESH or TESTED
- zone state only uses bars closed by `asof_ms`
- BROKEN / FLIPPED original zones are excluded from the active map

`/market/klines` now also accepts optional `start_time_ms` and `end_time_ms` for historical chart windows.

## Validation

- Python compile: PASS
- dashboard JavaScript syntax: PASS
- git diff check: PASS
- live Binance reconstruction parity against frozen LQ-1 sample: PASS
- production trading authority: unchanged

## Interpretation boundary

The dashboard labels are research context, not execution rules.

LQ-2 specifically rejected a generic rule based only on distance to supply. The adverse candidate carried into the UI is the more specific condition:

`inside FRESH 15m supply`

The UI is intended to visually audit why some trades fail there and why some winners break or accept through the zone before LQ-3 decides whether any production gate is justified.