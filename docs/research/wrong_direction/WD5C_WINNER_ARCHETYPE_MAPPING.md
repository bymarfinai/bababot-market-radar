# WD-5C — Winner Archetype Mapping

Status: EXECUTED ON VPS `core-prod`  
Authority: RESEARCH ONLY  
Trading behavior changed: NO

## Goal

WD-5C maps the full frozen 2,175-trade cohort into winner/opportunity archetypes so the detector can eventually distinguish:

- big runner opportunities,
- ordinary runners,
- small-edge trades,
- recovered winners,
- clean winners,
- missed opportunities,
- and no-edge trades.

The core design principle is to separate **entry opportunity quality** from **exit capture quality**.

A trade that reaches +2% MFE and later closes negative is still an excellent entry opportunity and a poor capture outcome. It must not be lumped together with a true wrong-direction trade.

## Frozen cohort

- 2,175 closed PAPER trades
- WD-1/WD-2 frozen cutoff: `1790826404280`
- Stage11C V2-proven cohort
- all causal entry snapshots available
- all 2,175 rows pass the strict Stage11C decision-time causality audit

## Archetype dimensions

### 1. Opportunity tier — future MFE

- `BIG_RUNNER`: MFE >= 2.0%
- `RUNNER`: 1.0% <= MFE < 2.0%
- `SMALL_EDGE`: 0.5% <= MFE < 1.0%
- `BORDERLINE`: 0.35% <= MFE < 0.5%
- `NO_EDGE`: MFE < 0.35%

This is the primary entry-quality dimension.

### 2. Realized winner tier

- `BIG_REALIZED_WIN`: realized PnL >= +1.0%
- `MEDIUM_REALIZED_WIN`: +0.5% <= realized PnL < +1.0%
- `SMALL_REALIZED_WIN`: 0 < realized PnL < +0.5%
- `NON_WIN`: realized PnL <= 0

### 3. Path style

Mapped from WD-1:

- `RECOVERED_WINNER`
- `CLEAN_WINNER`
- `MISSED_OPPORTUNITY`
- `WRONG_DIRECTION`
- `STALL`

### 4. Capture efficiency

For trades with MFE >= 0.5%:

- `HIGH_CAPTURE_GE50`: realized/MFE >= 50%
- `MEDIUM_CAPTURE_25_50`: 25% <= realized/MFE < 50%
- `LOW_CAPTURE_LT25`: realized/MFE < 25%
- `MISSED`: final PnL <= 0

## Composite archetypes

Examples:

- `BIG_RUNNER_RECOVERED`
- `BIG_RUNNER_CLEAN`
- `BIG_RUNNER_MISSED`
- `RUNNER_RECOVERED`
- `RUNNER_CLEAN`
- `RUNNER_MISSED`
- `SMALL_EDGE_WIN`
- `SMALL_EDGE_FAILED`
- `NO_EDGE_NONWIN`

## Causal anatomy

Every trade is joined to the WD-5A-style pre-entry feature set.

Features are evaluated at the Stage11C decision timestamp and include:

- Stage 4 scores/components,
- signed 5m/15m/1h momentum,
- movement expansion,
- Stage 5 structure/flow/OI/regime,
- Stage11C evidence families,
- 1m/3m micro evidence.

Future MFE/MAE/PnL are used only as archetype labels.

## Pairwise anatomy comparisons

WD-5C measures causal entry separation for:

1. `BIG_RUNNER vs SMALL_EDGE`
2. `BIG_RUNNER vs NO_EDGE`
3. `BIG_REALIZED_WIN vs SMALL_REALIZED_WIN`
4. `CLEAN_WINNER vs RECOVERED_WINNER`
5. `BIG_RUNNER_WINNER vs BIG_RUNNER_MISSED`
6. `RUNNER_WINNER vs RUNNER_MISSED`

Numeric separation uses a rank/AUC-style probability effect.

Categorical separation uses weighted class-rate deviation.

Every feature is also checked across chronological fifths to expose unstable effects.

## Reproducibility

Code:

- `market_radar/wd5c_archetypes.py`
- `scripts/wd5c_archetypes.py`
- `tests/test_wd5c_archetypes.py`

Outputs:

- `/opt/core-app/data/wd5c_winner_archetypes.csv`
- `/opt/core-app/data/wd5c_winner_archetypes_results.json`

Focused WD-0 through WD-5C tests at completion: **44/44 PASS**.
