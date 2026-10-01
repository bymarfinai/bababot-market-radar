# WD-5H Stage 1 — Entry Thesis Reliability Labeling & Causal Feature Audit

Status: EXECUTED ON VPS `core-prod`  
Authority: RESEARCH ONLY  
Trading behavior changed: NO

## Goal

WD-5H Stage 1 prepares the full frozen 2,175-trade population for a selective high-precision WIN gate.

The purpose is to stop treating every losing trade as the same problem.

The full cohort is relabeled into four thesis classes:

- `VALID_WINNER`
- `RIGHT_THEN_FAILURE`
- `TRUE_WRONG_DIRECTION`
- `STALL_NO_EDGE`

Stage 1 is an audit stage only. It does not train or promote an entry gate.

## Label definition

### VALID_WINNER

Merged from WD-1:

- `CORRECT_RUNNER`
- `RECOVERED_DRAWDOWN`

N = 500.

These are the trades the future selective gate should preserve and prioritize.

### RIGHT_THEN_FAILURE

N = 660.

These trades had a valid initial thesis / meaningful favorable path but later failed.

They should not automatically be treated as wrong-direction entries.

### TRUE_WRONG_DIRECTION

N = 849.

These are the strict low-MFE adverse trades that the earlier WD program targeted for reverse or no-trade treatment.

### STALL_NO_EDGE

N = 166.

These trades did not develop enough favorable edge.

## Full causal feature expansion

Stage 1 reconstructs all major evidence families for all 2,175 trades.

### Existing causal features

- Stage 4 score/components
- movement / momentum / activity
- Stage 5 structure, taker flow, OI, regime
- Stage11C evidence families
- WD-5D engineered overheat / acceleration / divergence features

### Full-population pre-entry 1m micro path

All 2,175 trades receive a causal pre-entry micro-path ending at the Stage11C decision timestamp.

Features include:

- 1m / 3m / 5m / 10m / 15m / 30m side returns
- momentum decay
- distance to selected-side local extreme
- candle body / close location / rejection wick
- range / volume climax and fade
- taker-share dynamics
- VWAP extension
- micro reversal pressure

### Market-relative features

BTCUSDT, ETHUSDT, BNBUSDT, and SOLUSDT are reconstructed across the full frozen time window.

Features include:

- market median selected-side returns
- breadth / alignment
- market dispersion
- coin minus market returns
- beta to BTC
- beta-adjusted residual return
- relative overextension

### Full-population OI dynamics

Historical 5m OI is reconstructed for all 2,175 trades.

Features include:

- current 5m OI change
- previous 5m OI change
- OI acceleration
- 15m / 30m OI change
- OI unwind / crowding interactions

## Coverage

- trades: 2,175 / 2,175
- pre-entry micro cache: 2,175 / 2,175
- OI cache: 2,175 / 2,175
- OI rows with fewer than 3 history points: 0
- micro rows with fewer than 16 bars: 0
- causal gate range: 2026-09-29 through 2026-10-01

## Audited feature space

Total portable research features: **207**

Approximate family counts:

- Stage 4 score: 15
- movement: 12
- Stage 5 context: 22
- Stage11C: 38
- WD-5D engineered: 27
- micro path: 31
- market relative: 21
- flow / structure: 19
- OI dynamics: 9
- other portable features: 13

Time features, latency features, and raw scale proxies are excluded from the primary portable audit.

## Pairwise audits

Stage 1 evaluates:

1. `VALID_WINNER vs ALL_NONWIN`
2. `VALID_WINNER vs TRUE_WRONG_DIRECTION`
3. `VALID_WINNER vs RIGHT_THEN_FAILURE`
4. `VALID_WINNER vs STALL_NO_EDGE`
5. `TRUE_WRONG_DIRECTION vs RIGHT_THEN_FAILURE`

Each feature is measured using:

- rank/AUC-style numeric separation or categorical class-rate separation,
- five chronological blocks,
- median block separation,
- minimum block separation,
- numeric direction consistency.

A feature is considered stable for descriptive purposes when:

- median fifth separation >= 0.08,
- minimum fifth separation >= 0.03,
- numeric direction is consistent across available fifths.

These criteria are for Stage 1 feature audit only and do not authorize a model.

## Key methodological conclusion

The direct binary target:

`VALID_WINNER vs ALL_NONWIN`

has only a small set of fully stable features.

However, pairwise separation is much stronger when the non-winner classes are kept distinct.

Therefore the Stage 1 architecture conclusion is:

> Do not force one flat WIN-vs-ALL classifier.

The next detector should be hierarchical and separately reject:

- TRUE_WRONG_DIRECTION,
- RIGHT_THEN_FAILURE,
- STALL_NO_EDGE,

before issuing a high-confidence `WIN / TAKE TRADE` decision.

## Reproducibility

Code:

- `market_radar/wd5h_stage1.py`
- `scripts/wd5h_stage1.py`
- `tests/test_wd5h_stage1.py`

Outputs:

- `/opt/core-app/data/wd5h1_preentry_1m_cache.jsonl`
- `/opt/core-app/data/wd5h1_benchmark_1m_cache.json`
- `/opt/core-app/data/wd5h1_oi_5m_cache.jsonl`
- `/opt/core-app/data/wd5h1_thesis_labeled_features.csv`
- `/opt/core-app/data/wd5h1_feature_audit_results.json`

Focused WD-0 through WD-5H Stage 1 tests: **72/72 PASS**.
