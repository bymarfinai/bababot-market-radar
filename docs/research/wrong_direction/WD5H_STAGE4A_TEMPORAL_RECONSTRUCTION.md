# WD-5H Stage 4A — Causal Temporal Feature Reconstruction

Status: EXECUTED ON VPS core-prod
Authority: RESEARCH ONLY
Production behavior changed: NO

## Goal

Build a causal feature matrix that describes how the original Market Detector
candidate evolves during a bounded confirmation window.

Stage 4A does not train a model and does not select any threshold.

## T0 definition

T0 is the latest Stage11C ENTER checked_at_ms at or before the historical
position open.

Audit result:

- coverage: 2,175 / 2,175
- checked_at_ms equals entry_latency.stage11c_finished_at_ms: 100%
- median Stage11C-to-fill latency: 200 ms
- p90 latency: 389 ms

Therefore the temporal window is anchored to the actual gate decision rather
than the later paper fill.

## Horizons

Frozen horizons:

- T+1 minute
- T+2 minutes
- T+3 minutes

For every horizon, only 1-minute candles whose close timestamp is less than or
equal to the target timestamp are allowed.

Partially formed candles are never used.

## Feature construction

For each horizon, Stage 4A combines the frozen causal pre-entry history with
only newly closed post-candidate candles and recomputes:

### Micro / path

- selected-side returns;
- local-extreme distance;
- CLV/body/wick behavior;
- range/volume/trade expansion;
- VWAP extension;
- reversal pressure.

### Direct confirmation path

- cumulative side-adjusted return from gate price;
- post-candidate MFE;
- post-candidate MAE;
- aggregate selected-side taker share;
- post-candidate volume/trade count;
- latest selected CLV/body/rejection wick.

### Market-relative

Recomputed using BTCUSDT, ETHUSDT, BNBUSDT, and SOLUSDT 1m benchmarks through
the exact target timestamp.

### Taker / flow

Recomputed using only fully closed 1m data through the horizon.

### Open interest

Historical Binance open-interest data is available at 5-minute resolution.

Only OI rows with timestamp <= horizon target are allowed.

Fresh OI-point availability is explicitly recorded and must not be assumed.

### Change versus T0

A curated set of micro, flow, market-relative, and OI features has a delta
column versus the original Stage 4A T0/pre-entry feature value.

## Causality guards

- no 1m candle with close_time > target;
- no OI row with timestamp > target;
- target timestamp anchored to exact Stage11C ENTER;
- future triple-barrier labels are carried only as labels for later Stage 4B,
  never as feature inputs.

## Reproducibility

Code:

- research/wrong_direction/wd5h_stage4a.py
- research/wrong_direction/scripts/wd5h_stage4a.py
- research/wrong_direction/tests/test_wd5h_stage4a.py

Frozen data:

- /opt/core-app/data/wd5h4a_temporal_features.csv
- /opt/core-app/data/wd5h4a_temporal_feature_results.json
- /opt/core-app/data/wd5h4a_benchmark_1m_cache.json
- /opt/core-app/data/wd5h4a_oi_5m_cache.jsonl
