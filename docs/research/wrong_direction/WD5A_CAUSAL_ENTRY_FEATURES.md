# WD-5A — Causal Entry Feature Reconstruction

Status: EXECUTED ON VPS `core-prod`  
Authority: RESEARCH ONLY  
Trading behavior changed: NO

## Goal

WD-5A converts the 849 WD-4 resolution targets into a clean supervised dataset whose features are available **before the Stage11C ENTER decision is handed off to execution**.

This stage does not fit a classifier and does not tune a trading rule.

## Target labels

WD-4 supplies three future-path target bands per trade:

- strict 1:1: TP +0.5% before SL -0.5%
- extended stop: TP +0.5% before SL -1.0%
- robust 1:1: TP +1.0% before SL -1.0%

Primary WD-5B target is the strict 1:1 label:

- `OPPOSITE_FROM_ENTRY_WIN`: 435
- `NO_TRADE_TARGET`: 386
- `FLIP_1M_WIN`: 14
- `FLIP_3M_WIN`: 14

## Decision-time causality boundary

The feature cutoff is:

> latest causal Stage11C `ENTER` revalidation `checked_at_ms <= position fill`.

Feature timestamps are audited against that Stage11C decision timestamp, not merely against the later position fill.

All 849 rows pass this stricter causal audit.

The audit also proves that:

- `order_created_at_ms` occurs after the decision cutoff for 849/849 trades.
- `position_opened_at_ms` occurs after the decision cutoff for 849/849 trades.

Therefore post-gate/fill timing fields are excluded from the model feature set.

## Explicit leakage exclusions

WD-5A does not expose as model features:

- close timestamp
- realized PnL / realized PnL %
- exit price
- MFE / MAE
- WD-1 outcome label
- WD-4 future-path best PnL
- WD-4 future target-hit timestamps
- order-to-fill / gate-to-fill / signal-to-fill latency
- position-opened timestamp
- free-text parameterized reasons
- symbol / signal ID / position ID

WD-4 future paths are used only to create target columns.

## Feature families

Reconstructed causal features include:

- Stage 4 LONG/SHORT scores
- selected-side vs opposite-side score components
- score-component deltas
- 5m / 15m / 1h / 24h returns and selected-side-adjusted returns
- movement stage / state / directional persistence
- volume / range / trade-count / return expansion
- Stage 5 market structure
- taker flow
- raw OI interpretation
- funding
- completed 4H market regime context
- Stage11C 1m/3m direction evidence
- price drift and impulse concentration
- Stage11C PRICE / FLOW / POSITIONING / REGIME families
- positioning detail
- Stage11C reason flags
- AI execution latency
- Stage11C processing latency
- causal decision-time cyclic hour/day features

## Dataset shape

Raw reconstructed feature columns: 121.

- numeric: 107
- categorical: 14
- missing values: 0

Ten constant columns are retained in the raw export for auditability but excluded from the model-ready list.

Model-ready nonconstant feature count: **111**.

## Constant features excluded from modeling

- `f_is_moving`
- `f_gate_soft_chase_threshold_pct`
- `f_gate_ret3_aligned`
- `f_gate_ret3_opposite`
- `f_gate_opposite_micro_structure`
- `f_gate_near_entry_support`
- `f_gate_price_family`
- `f_score_component_opposite_persistence`
- `f_score_component_opposite_timeframe_consistency`
- `f_gate_reason_family_price_structure_aligned`

## Reproducibility

Code:

- `market_radar/wd5a_features.py`
- `scripts/wd5a_features.py`
- `tests/test_wd5a_features.py`

VPS outputs:

- `/opt/core-app/data/wd5a_causal_entry_features.csv`
- `/opt/core-app/data/wd5a_causal_entry_features.jsonl`
- `/opt/core-app/data/wd5a_feature_manifest.json`

Focused WD-0 through WD-5A tests: **32/32 PASS**.
