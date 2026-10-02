# WD-5H Stage 4D — Delayed-Entry Economic Replay

Status: EXECUTED ON VPS core-prod
Authority: RESEARCH ONLY
Production behavior changed: NO

## Goal

Test whether the exact frozen Stage 4C temporal gate remains economically
useful when capital is actually deployed only after confirmation.

## Frozen gate

No retuning is allowed.

- horizon: T+3 minutes
- threshold: 0.6028066188778062
- frozen selected candidates: 62
  - validation: 37
  - historical test: 25

## Delayed entry price

For each selected candidate, Stage 4D fetches the first Binance futures
aggTrade with timestamp >= exact T0+3m.

Coverage:

- 62 / 62 candidates
- median wait after exact T+3 target: 743.5 ms
- p90: 4,797 ms
- maximum: 16,321 ms

This avoids using a candle open/close proxy for the delayed market entry.

Historical per-position fee and slippage assumptions are then applied.

## Economic replay

From the delayed market entry:

- upper barrier: net +0.5%
- lower barrier: net -0.5%
- vertical barrier: 30 minutes
- path: 1-minute close-confirmed

The gate, horizon, and score threshold remain frozen.

## Additional diagnostics

Stage 4D also measures:

- selected-side price degradation from original entry to delayed entry;
- label transitions from original Stage 3A label to delayed-entry label;
- zero-cost sensitivity;
- 60-minute close-based runner retention;
- early T+3 resolution opportunity cost.

## Reproducibility

Code:

- research/wrong_direction/wd5h_stage4d.py
- research/wrong_direction/scripts/wd5h_stage4d.py
- research/wrong_direction/tests/test_wd5h_stage4d.py

Frozen outputs:

- /opt/core-app/data/wd5h4d_delayed_entry_replay.csv
- /opt/core-app/data/wd5h4d_delayed_entry_results.json
- /opt/core-app/data/wd5h4d_delayed_entry_agg_cache.jsonl
