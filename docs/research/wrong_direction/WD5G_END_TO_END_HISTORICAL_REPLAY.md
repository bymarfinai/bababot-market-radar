# WD-5G — End-to-End Historical Replay

Status: EXECUTED ON VPS `core-prod`  
Authority: RESEARCH ONLY  
Trading behavior changed: NO

## Goal

WD-5G performs a full 2,175-trade historical replay of the candidate architecture produced by WD-5D through WD-5F.

The frozen policy is:

- if `overheat_pressure < 5.481925222153388` -> KEEP original side
- if overheated:
  - if frozen WD-5F market-relative reversal probability >= 0.5142449163777649 -> REVERSE
  - otherwise -> SKIP / NO TRADE

## Replay population

- 2,175 frozen PAPER trades
- 967 classified as overheated
- 1,208 classified as healthy/cool

All 967 overheated trades receive:

1. causal pre-entry 1m reconstruction,
2. frozen WD-5F market-relative score,
3. 30-minute post-entry 1m counterfactual opposite-side path.

## Reverse execution model

For a REVERSE action:

- opposite position is opened from the original entry,
- notional = $500,
- same fee/slippage assumptions as WD-4,
- 30-minute horizon,
- +0.5% net TP,
- -0.5% net SL,
- if neither threshold is reached, close at the 30-minute horizon.

This preserves the WD-4 strict bounded-risk concept.

## Comparisons

WD-5G compares three policies.

### Baseline

Keep every observed historical trade.

### Health-only ablation

- healthy -> KEEP
- overheated -> SKIP

This isolates the value of the overheat detector.

### WD-5G primary

- healthy -> KEEP
- overheated + confirmed reversal -> REVERSE
- overheated without confirmation -> SKIP

## Promotion requirements

The end-to-end candidate is not considered ready unless all of the following hold:

- better PnL than baseline,
- not worse than health-only,
- >=50% of TRUE_WRONG_DIRECTION converted to WIN or SKIP,
- >=80% of runner opportunities kept on original side,
- >=80% of realized winners kept on original side,
- reverse execution aggregate PnL nonnegative.

## Important caveat

WD-5F's one-sided objective was formalized after the first symmetric WD-5F holdout was inspected.

Therefore WD-5G is a research replay, not an untouched production-promotion test.

## Reproducibility

Code:

- `market_radar/wd5g_replay.py`
- `scripts/wd5g_replay.py`
- `tests/test_wd5g_replay.py`

Outputs:

- `/opt/core-app/data/wd5g_preentry_1m_cache.jsonl`
- `/opt/core-app/data/wd5g_postentry_1m_cache.jsonl`
- `/opt/core-app/data/wd5g_end_to_end_replay_rows.csv`
- `/opt/core-app/data/wd5g_end_to_end_replay_results.json`

Focused WD-0 through WD-5G tests at completion: **67/67 PASS**.
