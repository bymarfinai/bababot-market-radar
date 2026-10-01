# WD-2 — Wrong-Direction Anatomy

Status: EXECUTED ON VPS `core-prod`  
Authority: RESEARCH ONLY  
Trading behavior changed: NO

## Goal

Determine where TRUE_WRONG_DIRECTION separates from recoverable early adverse movement and correct runners.

WD-2 does not tune Stage 2, Stage 4, Stage 6, Stage 11C, or Stage 12. It measures:

1. entry-state separation,
2. Stage 11C evidence-family leakage,
3. segment-specific wrong-direction rates,
4. post-entry divergence by horizon.

## Frozen source cohort

WD-2 uses the WD-1 frozen cohort:

- `closed_at_ms <= 1790826404280`
- 2026-10-01 10:46:44.280 WIB
- 2,175 closed PAPER trades
- `POST_ENTRY_REBUILD`
- proven `stage11c-v2-evidence-families`
- 0 missing Stage 11C entry snapshots

## Entry anatomy

Entry features come only from information available at or before fill:

- Stage 4 directional scores
- Stage 5/6 context
- 5m / 15m / 1h side-adjusted momentum
- movement stage
- volume / range / trade-count expansion
- structure / taker / raw OI / regime
- Stage 11C 1m / 3m side returns
- Stage 11C price drift
- PRICE / FLOW / POSITIONING / REGIME families
- signal / approval / AI / Stage 11C / fill latency

Numeric separation uses the Mann-Whitney probability effect transformed to a 0–1 separation score:

`abs(P(comparator > wrong) - 0.5) * 2`

0 means no rank separation; 1 means perfect separation.

## Horizon anatomy

Two lanes are retained deliberately.

### Event-driven Stage 12 lane

The ordinary `position_evaluations` stream is useful for coverage and lifecycle context, but it is event-driven. A row before +3m is not automatically treated as an exact +3m measurement.

### High-resolution PP observation lane

Primary exact-horizon work uses `pp_decision_v2_observations`:

- approximately 15-second observation stream,
- observation must be within +/-45 seconds of the requested target,
- trades already closed before the target are counted as terminal and not carried forward with a stale snapshot.

Coverage of this high-resolution lane is deployment-period dependent:

| Label | Full cohort | High-res observed | Coverage |
|---|---:|---:|---:|
| TRUE_WRONG_DIRECTION | 849 | 522 | 61.5% |
| RECOVERED_DRAWDOWN | 385 | 261 | 67.8% |
| STALL_NO_EDGE | 166 | 105 | 63.3% |
| RIGHT_THEN_FAILURE | 660 | 424 | 64.2% |
| CORRECT_RUNNER | 115 | 39 | 33.9% |

Therefore high-resolution comparisons are strongest for TRUE_WRONG_DIRECTION vs RECOVERED_DRAWDOWN. CORRECT_RUNNER horizon results are supplemental because coverage is lower.

## Reproducibility

Code:

- `market_radar/wd2_anatomy.py`
- `scripts/wd2_anatomy.py`
- `tests/test_wd2_anatomy.py`

Frozen machine-readable output on VPS:

`/opt/core-app/data/wd2_anatomy_results.json`

Validation at completion:

- WD-2 + WD-1 + WD-0 focused tests: 17/17 PASS
- production app restart: NO
- trading authority change: NO
