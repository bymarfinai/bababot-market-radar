# Market Detector Research State

Last frozen state: 2026-10-01

## Current Next Stage

WD-5H Stage 4B — Temporal Confirmation Pattern Discovery

Stage 4A is complete.

The static pre-entry path was closed after Stage 3C failed to produce a stable
high-precision pocket.

Stage 4A reconstructed exact causal temporal snapshots at:

- T+1 minute
- T+2 minutes
- T+3 minutes

where T0 is the exact latest Stage11C ENTER decision timestamp.

## Stage 4A Frozen Reconstruction

Coverage:

- rows: 2,175 / 2,175
- exact Stage11C timestamp match: 2,175 / 2,175
- causality violations: 0
- pre-entry cache coverage: 2,175 / 2,175
- post-entry 1m cache coverage: 2,175 / 2,175
- OI cache coverage: 2,175 / 2,175
- benchmark symbols: BTC, ETH, BNB, SOL

Temporal feature matrix:

- 351 output columns
- 330 temporal feature columns
- 110 temporal feature columns per horizon

Each horizon contains:

- micro/path state;
- market-relative state;
- taker/flow state;
- OI state;
- direct confirmation-path features;
- deltas versus T0.

No model was trained and no threshold was selected in Stage 4A.

## Important Stage 4A Findings

1. T0 can be reconstructed exactly. The latest Stage11C ENTER checked_at_ms
   equals stage11c_finished_at_ms for all 2,175 trades.
2. Median Stage11C-to-fill latency is 200 ms; p90 is 389 ms.
3. Strict closed-bar causality works cleanly:
   - T+1: 2,173 trades have one new closed 1m bar; 2 have zero because their
     exact target occurs milliseconds before the next candle close.
   - T+2: 2,173 have two; the same 2 have one.
   - T+3: 2,173 have three; the same 2 have two.
   These are boundary effects, not missing exchange data.
4. Historical OI has 5-minute resolution and contributes almost no fresh
   information inside the 1-3 minute confirmation window:
   - T+1: 0 trades receive a new OI point;
   - T+2: 0;
   - T+3: only 52 / 2,175 = 2.39%.
   OI can remain context, but should not be treated as a primary temporal
   confirmation signal at this horizon.
5. Price path, taker flow, microstructure, and market-relative movement are
   therefore the main temporal evidence families for Stage 4B.

## Production State

UNCHANGED.

No Stage 4A feature or rule has production authority.

## Completed Current Program

- WD-5H Stage 3A — COMPLETE: META_LABEL_RESET_COMPLETE
- WD-5H Stage 3B — COMPLETE: META_RANKING_SIGNAL_WEAK
- WD-5H Stage 3C — REJECTED: STATIC_HIGH_PRECISION_GATE_NOT_READY
- WD-5H Stage 3D — SKIPPED
- WD-5H Stage 3E — NOT APPLICABLE
- WD-5H Stage 4A — COMPLETE: TEMPORAL_FEATURE_RECONSTRUCTION_COMPLETE

## Next Research Question

Stage 4B must compare META_WIN versus META_LOSS separately at T+1, T+2, and
T+3 to identify which temporal evidence actually strengthens discrimination.

Do not select a production threshold in Stage 4B.

## Parked

- Wallet/on-chain fusion.

## Source of Truth

Detailed experiment history:
docs/research/WD_RESEARCH_LEDGER.md

Historical methodology/results:
docs/research/wrong_direction/

Research code:
research/wrong_direction/
