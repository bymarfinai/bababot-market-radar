# LQ-1 — Causal Structural Liquidity Reconstruction

Status: **PASS / FROZEN FOR LQ-2**

Version: `lq1-causal-structural-liquidity-v1`

## Objective

Build a reproducible structural supply/demand map for the frozen 1,236 resolved LONG universe **without using any candle that had not closed at the trade snapshot timestamp**.

LQ-1 does **not** optimize against MFE, PnL, winner labels, or any future outcome. Its only job is to produce a causal market-location dataset that LQ-2 can test.

## Frozen universe

- LONG trades: **1,236 / 1,236**
- Unique symbols: **400**
- Source: `/opt/core-app/data/wd5h4a_temporal_features.csv`
- Snapshot anchor: actual position `opened_at_ms`
- Price anchor: actual `positions.entry_price`
- Timeframes: **5m / 15m / 1h**
- Binance historical symbol errors: **0**

## Causal zone definition

A zone is not visible at the swing candle itself.

For each timeframe:

1. Candidate base must be a local swing against the previous 3 bars and the following 2 bars.
2. The following 2 bars must have **already closed**.
3. Departure from the base must be at least **0.75 ATR**.
4. Supply boundaries are base body-top → wick high.
5. Demand boundaries are wick low → base body-bottom.
6. `born_ms` is the close timestamp of the second confirmation/departure bar.
7. A snapshot may only use zones where `born_ms <= asof_ms`.
8. Zone state is updated only with bars where `close_ms <= asof_ms`.

State vocabulary:

- `FRESH` — no post-birth retest
- `TESTED` — retested but not structurally broken
- `BROKEN` — closed through the distal boundary
- `FLIPPED` — broken and later causally retested from the opposite side

Broken/flipped zones are excluded from the active nearest-zone map for their original role.

## Coverage

| Metric | Result |
|---|---:|
| Position coverage | **1,236 / 1,236** |
| Nearest overhead supply | **1,176 / 1,236 (95.15%)** |
| Nearest demand below / containing entry | **1,234 / 1,236 (99.84%)** |
| Both supply + demand available | **1,174 / 1,236 (94.98%)** |
| Entry inside at least one active supply zone | **557** |
| Entry inside at least one active demand zone | **23** |
| Symbol fetch errors | **0** |
| Causality invariant violations | **0** |

Candidate zones reconstructed across the fetched history:

- 5m: **42,751**
- 15m: **21,964**
- 1h: **11,147**

## Supply-map sanity diagnostics

The high number of entries inside an active supply zone was checked for obvious over-wide-zone artifacts.

| TF | Supply coverage | Inside supply | Median distance | Median width | P90 width | Median active zones |
|---|---:|---:|---:|---:|---:|---:|
| 5m | 1,012 | 266 | 0.321% | 0.502 ATR | 1.181 ATR | 4 |
| 15m | 1,115 | 310 | 0.559% | 0.481 ATR | 1.195 ATR | 4 |
| 1h | 1,146 | 360 | 0.895% | 0.569 ATR | 1.321 ATR | 3 |

Combined nearest-supply timeframe:

- 1h: **544**
- 15m: **298**
- 5m: **334**

Combined nearest-supply median distance is **0.0423%** because many entries are already inside an active zone. This is **not interpreted as predictive evidence in LQ-1**; it is deliberately preserved for LQ-2.

## Frozen output fields

The trade-level CSV contains, per timeframe:

- active supply/demand count
- nearest zone lower / upper
- entry-to-zone distance %
- departure strength in ATR
- base volume ratio
- zone width in ATR
- touch count
- state
- zone birth timestamp

It also contains combined:

- `nearest_supply_distance_pct`
- `nearest_supply_timeframe`
- `nearest_supply_lower / upper`
- `nearest_supply_departure_atr`
- `nearest_supply_touch_count`
- `nearest_supply_state`
- corresponding nearest-demand fields

## Validation

Synthetic causal test: **PASS**

Full entry-snapshot invariants:

- no nearest zone born after the position open timestamp
- no negative nearest-zone distance
- all 1,236 frozen LONG trades retained

Result: **PASS**

## Interpretation boundary

LQ-1 proves that a high-coverage, timestamp-safe structural liquidity map can be reconstructed for the frozen LONG universe.

It does **not** yet prove that nearby supply causes low MFE.

That is LQ-2:

> Compare MFE buckets and trade classes against entry-to-supply headroom, zone state, timeframe, departure strength, and demand/supply geometry.

No production order authority is changed by LQ-1.