# WD-3 — Counterfactual Direction Fix

Status: EXECUTED ON VPS `core-prod`  
Authority: RESEARCH ONLY  
Trading behavior changed: NO

## Goal

WD-3 tests the two repair paths implied by WD-2:

1. **Delay / confirm entry** for 1–3 minutes.
2. **Enter immediately, then dynamically close wrong-direction positions** during the first 1–3 minutes.

The objective is not to maximize historical PnL blindly. The key trade-off is loss saved versus damage to `RECOVERED_DRAWDOWN` and `CORRECT_RUNNER`.

## Frozen cohort

- WD-1 / WD-2 frozen cutoff: `1790826404280`
- 2,175 closed PAPER trades
- Stage 11C V2 proven cohort
- actual frozen net PnL: **-$2,338.6495**

The high-resolution lane is `pp_decision_v2_observations`. A horizon observation is usable only when it is within +/-45 seconds of the requested target.

Unmatched trades are left at actual PnL. This makes full-cohort deltas conservative with respect to pre-observation-era trades.

## Dynamic-exit replay

Dynamic-exit replay keeps:

- the actual entry fill,
- the actual initial quantity,
- all REDUCE fills executed before the tested horizon,
- recorded entry-fee allocation,
- recorded fee rate,
- recorded slippage.

When a tested signature fires, only the remaining quantity is closed at the observed horizon market price with the recorded fee/slippage model.

This is materially closer to executable economics than a simple PnL-threshold comparison.

## Delay-entry benchmark

For observable trades:

- flagged trade -> skip / PnL = 0,
- unflagged trade -> enter $500 notional at the observed horizon market price,
- exit at the original trade's final market censor with recorded fee/slippage.

This is a **fixed-censor benchmark**, not a full lifecycle replay. It is useful for answering whether waiting improves entry economics, but it is not promotion-grade evidence by itself.

## Tested signatures

At 1m / 3m / 5m:

- `ret3neg_and_flow_opp`
- `ret3neg_and_positioning_opp`
- `ret3neg_and_micro_opp`
- `adverse_families_ge_2`
- `adverse_families_ge_3`
- `danger_ge_2`
- `danger_ge_4`
- `pnl_le_minus_035`
- `pnl_le_minus_035_and_adverse_ge_2`

Single-horizon grid:

- 3 horizons × 9 signatures × 2 policy types = 54 counterfactuals.

Sequential grid:

- all 9 one-minute signatures × all 9 three-minute signatures = **81 sequential dynamic-exit policies**.

## Robustness

Top candidates are rechecked on chronological thirds of the **actually observable horizon cohort**, not thirds of the full historical dataset.

This corrects for the fact that the high-resolution PP observation lane was activated later than the start of the frozen 2,175-trade cohort.

## Reproducibility

Code:

- `market_radar/wd3_counterfactual.py`
- `scripts/wd3_counterfactual.py`
- `tests/test_wd3_counterfactual.py`

Frozen machine-readable result on VPS:

`/opt/core-app/data/wd3_counterfactual_results.json`

Focused WD-0 → WD-3 tests at completion: **22/22 PASS**.
