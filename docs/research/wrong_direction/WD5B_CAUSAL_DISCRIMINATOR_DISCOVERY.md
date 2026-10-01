# WD-5B — Causal Discriminator Discovery

Status: EXECUTED ON VPS `core-prod`  
Authority: RESEARCH ONLY  
Trading behavior changed: NO

## Goal

WD-5B tests whether the causal pre-entry feature set reconstructed in WD-5A can distinguish:

- `OPPOSITE_FROM_ENTRY_WIN`
- `NO_TRADE_TARGET`

without using future information.

The two small early-flip classes are excluded from the primary binary discriminator:

- `FLIP_1M_WIN`: 14
- `FLIP_3M_WIN`: 14

Primary binary cohort:

- 435 OPPOSITE_FROM_ENTRY_WIN
- 386 NO_TRADE_TARGET
- total: 821

## Chronological design

Rows are ordered by actual position open time.

- first 40% / 328 trades: inner training
- next 20% / 164: inner validation for feature-count / regularization selection
- first 60% / 492: refit development model
- next 20% / 164: outer validation for decision-threshold selection
- final 20% / 165: untouched final test

The final test is not used to choose features, model hyperparameters, or thresholds.

## Feature variants

### Portable market — primary

Starts from WD-5A model-ready causal features and excludes:

- time-of-day / weekday
- processing-latency features
- absolute scale proxies such as raw quote volume and raw EMA price levels

This leaves 100 candidate features.

### Full causal — sensitivity only

All 111 WD-5A nonconstant causal features.

This variant is reported to check whether infrastructure timing / time-window / scale proxies materially improve separation.

## Model families

WD-5B deliberately uses multiple model classes.

### Regularized logistic model

- train-only univariate feature ranking
- top-k search
- L2 regularization search
- chronological validation
- standardized numeric features
- train-only categorical encoding

### Shallow randomized forest

Used to test nonlinear interactions such as:

- evidence-family combination × momentum
- structure × taker flow
- OI interpretation × regime
- score component × current side

Hyperparameters are selected only on inner chronological validation.

### Stability-selected models

A separate robustness variant selects only features whose separation remains present across all three chronological DEV blocks.

Numeric features must also retain the same direction of association.

## Decision triage

The classifier is also tested as a three-way decision:

- high score -> REVERSE
- low score -> NO TRADE
- middle -> ABSTAIN

Thresholds are chosen only on outer validation.

The search attempts progressively lower two-sided precision floors:

80%, 75%, 70%, 65%, 60%.

A model is not considered robust merely because one action has high precision in the final test.

## Novel-symbol sensitivity

The untouched final test contains 33 trades from 30 symbols never seen in train or validation.

This subset is reported separately to detect symbol memorization.

## Research sufficiency principle

Final-test improvement cannot override an outer-validation failure.

The WD-5B conclusion is therefore based on:

1. chronological inner validation,
2. outer validation,
3. threshold stability,
4. final untouched test,
5. novel-symbol sensitivity.

## Reproducibility

Code:

- `market_radar/wd5b_discovery.py`
- `scripts/wd5b_discovery.py`
- `tests/test_wd5b_discovery.py`

Machine-readable result:

`/opt/core-app/data/wd5b_discriminator_results.json`

Focused WD-0 through WD-5B tests: **39/39 PASS**.
