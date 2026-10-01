# WD-5H Stage 3A — Triple-Barrier Meta-Label Reset

Status: EXECUTED ON VPS core-prod
Authority: RESEARCH ONLY
Production behavior changed: NO

## Goal

Replace the old historical realized-PnL entry target with a standardized
economic path label.

The existing Market Detector remains the primary side model. It already
produces LONG/SHORT candidates.

Stage 3A asks only:

After the historical entry, did that selected side reach a predefined
favorable net barrier before reaching a symmetric invalidation barrier?

No model is trained in Stage 3A.

## Frozen primary barrier

The primary barrier was frozen before inspecting Stage 3A results:

- TP: net +0.5%
- SL: net -0.5%
- horizon: 30 minutes
- notional: $500
- fees: per-position historical fee_rate, fallback 0.00075
- slippage: per-position historical slippage_bps, fallback 2 bps
- path resolution: 1-minute close-confirmed
- entry origin: actual historical paper-entry timestamp / entry market price

This configuration mirrors the +0.5/-0.5 bounded economic criterion already
used in WD-4 and was not selected from Stage 3A label performance.

## Label definition

META_WIN: net +0.5% is reached before net -0.5%.

META_LOSS: net -0.5% is reached before net +0.5%.

TIMEOUT: neither barrier is reached before 30 minutes.

TIMEOUT remains distinct and must not be silently merged into META_LOSS.

## Sensitivity configurations

- +0.5% / -0.5% / 60m
- +1.0% / -1.0% / 30m
- +1.0% / -1.0% / 60m

These are descriptive robustness checks only.

## Overlap / uniqueness

For the primary label each event interval runs from opened_at_ms to first
barrier touch or the 30-minute vertical barrier.

Minute-level concurrency and event uniqueness weights are calculated now so
Stage 3B can use purging, embargo, and uniqueness weighting.

## Reproducibility

Code:
- research/wrong_direction/wd5h_stage3a.py
- research/wrong_direction/scripts/wd5h_stage3a.py
- research/wrong_direction/tests/test_wd5h_stage3a.py

Frozen outputs:
- /opt/core-app/data/wd5h3a_postentry_1m_cache.jsonl
- /opt/core-app/data/wd5h3a_triple_barrier_labels.csv
- /opt/core-app/data/wd5h3a_triple_barrier_results.json
