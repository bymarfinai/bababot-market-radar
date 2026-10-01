# WD-5H Stage 3C Frozen Results — 2026-10-01

Source of truth: VPS core-prod
Authority: RESEARCH ONLY
Production changes: NONE

## Formal status

STATIC_HIGH_PRECISION_GATE_NOT_READY

## Primary architecture

BASELINE_UNPURGED_UNWEIGHTED

Frozen features:

1. f_ret_5m_pct_raw
2. f_median_abs_ret_5m_pct
3. f_gate_ret_3m_pct_raw
4. f_ret_1h_pct_for_selected
5. f_micro_selected_vwap_extension_20

Top-k: 5
L2: 4.0
Training resolved N: 1,153

## Precision floor search — primary model

### 50% floor

Validation threshold: 0.3561758075

Validation:
- TAKE: 18
- META_WIN: 9
- META_LOSS: 9
- precision: 50.0%
- coverage: 4.14%

Same threshold on test:
- TAKE: 15
- META_WIN: 4
- META_LOSS: 11
- precision: 26.67%
- standardized barrier net: -$17.50

### 60% floor

No validation threshold with >=10 resolved TAKEs.

### 65% floor

No validation threshold with >=10 resolved TAKEs.

### 70% floor

No validation threshold with >=10 resolved TAKEs.

### 75% floor

No validation threshold with >=10 resolved TAKEs.

### 80% floor

No validation threshold with >=10 resolved TAKEs.

## Best usable primary threshold

Validation:

- threshold: 0.3702932857
- TAKE: 11
- META_WIN: 6
- META_LOSS: 5
- precision: 54.55%
- coverage: 2.53%
- standardized barrier net: +$2.50

Same threshold on test:

- TAKE: 7
- META_WIN: 1
- META_LOSS: 6
- precision: 14.29%
- coverage: 1.61%
- standardized barrier net: -$12.50

The validation pocket does not generalize.

## Ultra-selective primary diagnostic

Allowing as few as 3 resolved validation TAKEs does not improve the best
primary-model precision beyond 54.55%.

Therefore the primary model does not even expose a tiny 60%+ validation pocket
under its actual score ordering.

## Purged + uniqueness weighted sensitivity

This architecture is diagnostic only and is not promotion eligible.

Usable minimum >=10 resolved TAKEs:

- best validation precision: 50.0% on 10 TAKEs;
- same threshold test: 18.18% on 11 TAKEs.

Ultra-selective minimum >=3:

Validation:
- threshold: 0.4660143441
- TAKE: 8
- META_WIN: 5
- META_LOSS: 3
- precision: 62.5%

Same threshold test:
- TAKE: 8
- META_WIN: 1
- META_LOSS: 7
- precision: 12.5%
- standardized barrier net: -$15.00

Even the diagnostic high-score tail collapses.

## Interpretation

Stage 3C closes the static pre-entry path.

The problem is no longer plausibly explained by:

- historical exit labels;
- obvious overlapping-window leakage;
- lack of uniqueness weighting;
- choosing a selective threshold instead of a global classifier.

After all of those corrections, the pre-entry snapshot still does not contain
a stable high-purity WIN pocket.

## Decision

Do not proceed to WD-5H Stage 3D.

An end-to-end replay is not useful because there is no validated Stage 3C gate
to replay.

Do not keep adding static indicators to the same timestamp.

The next preferred hypothesis is:

WD-5H Stage 4 — Causal 1–3 Minute Confirmation Window

Earlier WD-2/WD-3 research already showed materially stronger separation in
the first minutes after the candidate signal.

The next design should test whether delaying capital deployment for 1–3
minutes can trade off:

- higher WIN precision;
- fewer bad entries;
- delayed-entry slippage/opportunity cost;
- runner retention;
- trade/day.

## Frozen artifact hashes

wd5h3c_take_abstain_predictions.csv
SHA256: 00ea1c74f45fd6c09e1e5ea858f7a7263710e2f0dd0309df8b1695d07d5826cb

wd5h3c_take_abstain_results.json
SHA256: c1a7240777437bc326c959a998ed73c24fbb41b48d99fad3540c1a896a8730a2
