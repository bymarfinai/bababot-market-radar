# WD-5H Stage 2 — Hierarchical Thesis Classifier + High-Precision WIN Abstention Gate

Status: EXECUTED ON VPS `core-prod`  
Authority: RESEARCH ONLY  
Trading behavior changed: NO

## Goal

WD-5H Stage 2 tests whether the full causal feature set from Stage 1 can produce a selective entry gate that takes only high-confidence winners.

The design follows the Stage 1 conclusion:

> Do not train one flat WIN-vs-ALL classifier as the only decision layer.

Instead Stage 2 trains three separate pairwise heads:

1. `VALID_WINNER vs TRUE_WRONG_DIRECTION`
2. `VALID_WINNER vs RIGHT_THEN_FAILURE`
3. `VALID_WINNER vs STALL_NO_EDGE`

A trade is accepted only when it passes all three heads.

## Frozen population

Input:

`/opt/core-app/data/wd5h1_thesis_labeled_features.csv`

Rows: 2,175.

Class totals:

- VALID_WINNER: 500
- TRUE_WRONG_DIRECTION: 849
- RIGHT_THEN_FAILURE: 660
- STALL_NO_EDGE: 166

## Chronological split

No random shuffle is used.

- first 60% = training: 1,305
- next 20% = validation: 435
- final 20% = untouched test: 435

Training class counts:

- VALID_WINNER: 319
- TRUE_WRONG_DIRECTION: 498
- RIGHT_THEN_FAILURE: 389
- STALL_NO_EDGE: 99

Validation:

- VALID_WINNER: 95
- TRUE_WRONG_DIRECTION: 156
- RIGHT_THEN_FAILURE: 153
- STALL_NO_EDGE: 31

Test:

- VALID_WINNER: 86
- TRUE_WRONG_DIRECTION: 195
- RIGHT_THEN_FAILURE: 118
- STALL_NO_EDGE: 36

## Leakage control

Only features whose names begin with `f_` are eligible.

Excluded:

- future labels / future MFE / MAE / realized PnL
- time-of-day features
- latency features
- raw scale proxies such as absolute quote volume / EMA price levels

Portable feature count: 207.

## Model selection

Each pairwise head is trained only on:

- VALID_WINNER
- the head's single rejection class

The 60% training window is internally split chronologically:

- first 75% of the pairwise training cohort = inner train
- final 25% = inner model validation

Feature ranking is computed from inner train only.

Grid:

- top-k: 5 / 10 / 20 / 40 / 60 / 80
- L2: 0.1 / 1.0 / 4.0

The best configuration is selected using inner-validation AUC, then refit on the entire outer training window.

The outer validation 20% is never used for model feature selection.

## Hierarchical action

For every candidate the three pairwise models output:

- P(WINNER vs TRUE_WRONG)
- P(WINNER vs RIGHT_THEN_FAILURE)
- P(WINNER vs STALL)

Final TAKE requires all three scores to exceed validation-selected thresholds.

Otherwise:

`ABSTAIN / NO TRADE`

## Threshold selection

Thresholds are searched only on the outer validation window.

Primary search requires at least 5% validation coverage:

- minimum validation TAKE count = 22

Precision floors evaluated:

- 60%
- 65%
- 70%
- 75%
- 80%
- 85%
- 90%

For a feasible floor, the selected threshold combination maximizes TAKE count, then PnL, then precision.

No precision floor from 60% upward is feasible at the required minimum coverage.

The fallback candidate is therefore the highest-precision available gate under the minimum-coverage constraint.

## Flat baseline

Stage 2 also trains a direct:

`VALID_WINNER vs ALL_NONWIN`

logistic model using the identical chronological / train-only selection protocol.

This is used only as an architecture comparison.

## Post-hoc sensitivity

After the primary final test was inspected, two diagnostic checks were run:

1. ultra-selective threshold search allowing as few as 3 validation trades
2. nonlinear shallow random-forest pairwise heads

These checks are explicitly post-hoc and cannot be used for promotion.

They test whether the primary failure was merely caused by:

- the 5% minimum coverage,
- or linear-model underfitting.

Neither explanation rescues the gate.

## Reproducibility

Code:

- `market_radar/wd5h_stage2.py`
- `scripts/wd5h_stage2.py`
- `tests/test_wd5h_stage2.py`

Outputs:

- `/opt/core-app/data/wd5h2_selective_gate_predictions.csv`
- `/opt/core-app/data/wd5h2_selective_gate_results.json`

Focused WD-0 through WD-5H Stage 2 tests: **76/76 PASS**.
