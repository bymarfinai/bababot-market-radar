# WD-4 — Wrong-Direction Resolution Mapping

Status: EXECUTED ON VPS `core-prod`  
Authority: RESEARCH ONLY  
Trading behavior changed: NO

## Goal

WD-4 changes the question from:

> How much loss can be reduced?

to:

> For the 849 strict TRUE_WRONG_DIRECTION trades, which ones could have become real wins, and which ones should have been NO TRADE?

WD-4 is an outcome-resolution mapping stage. It does **not** claim the system can already identify the correct resolution causally at entry.

## Frozen cohort

- 849 `TRUE_WRONG_DIRECTION` trades
- frozen WD-1 / WD-2 cutoff: `1790826404280`
- all trades reconstructed from Binance USD-M Futures 1m klines
- 849 / 849 historical paths successfully cached
- primary horizon: 30 minutes after actual entry

Binance cache on VPS:

`/opt/core-app/data/wd4_wrong_direction_1m_cache.jsonl`

## Counterfactual paths

Each wrong-direction trade is evaluated under:

1. **Opposite from entry**
   - reverse LONG <-> SHORT at the original market-entry time,
   - $500 notional,
   - recorded fee rate and slippage.

2. **Flip after +1 minute**
   - keep the original entry,
   - close the original side at the first causal closed 1m candle after +1m,
   - open the opposite side,
   - cumulative sequence PnL includes original loss + all fees/slippage.

3. **Flip after +3 minutes**
   - same structure as +1m, but using the first causal closed 1m candle after +3m.

No future candle is used to choose the entry/flip price itself.

## Win definitions

WD-4 deliberately reports several levels.

### Weak net win

The cumulative counterfactual sequence becomes net positive after fee/slippage at a closed 1m candle.

This measures economic opportunity but is not the primary "truly saved" definition.

### Strong +0.5% win

The sequence reaches cumulative net +0.5% of $500 notional, or approximately +$2.50.

### Strict 1:1 target — primary actionable target

`TP +0.5% before SL -0.5%`

This is the primary WD-4 resolution target because the trade must reach the profit target before an equally sized adverse threshold.

### Extended-stop target

`TP +0.5% before SL -1.0%`

This tests whether the result survives a wider adverse band.

### Robust 1:1 target

`TP +1.0% before SL -1.0%`

This is the strongest fixed RR=1:1 sensitivity tested.

## Primary target labels

For the 30-minute horizon, every wrong-direction trade receives per-trade target labels:

- `OPPOSITE_FROM_ENTRY_WIN`
- `FLIP_1M_WIN`
- `FLIP_3M_WIN`
- `NO_TRADE_TARGET`

Labels are stored separately for:

- strict +0.5 / -0.5,
- extended +0.5 / -1.0,
- robust +1.0 / -1.0.

The strict target is the main handoff to WD-5.

## Critical causality limitation

These target labels are created from the future realized price path.

Therefore:

- WD-4 tells us **what resolution was economically possible**,
- WD-4 does **not** tell us yet how to choose that resolution in real time.

A statement such as "435 trades should have been reversed from entry" means 435 trades have a future path that supports that target. It does not mean Stage 4/6/11C currently possesses a causal rule that can identify those 435 without also damaging good trades.

That causal classification problem belongs to WD-5.

## Reproducibility

Code:

- `market_radar/wd4_resolution.py`
- `scripts/wd4_resolution.py`
- `tests/test_wd4_resolution.py`

Machine-readable result on VPS:

`/opt/core-app/data/wd4_resolution_results.json`

Focused WD-0 → WD-4 tests at completion: **27/27 PASS**.
