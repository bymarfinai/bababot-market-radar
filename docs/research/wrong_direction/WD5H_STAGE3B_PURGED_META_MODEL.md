# WD-5H Stage 3B — Purged Meta-Model + Overlap Uniqueness Weighting

Status: EXECUTED ON VPS core-prod
Authority: RESEARCH ONLY
Production behavior changed: NO

## Goal

Test whether the corrected Stage 3A target can be predicted from causal
pre-entry features once validation leakage from overlapping outcome windows is
controlled.

Binary target:

- positive = META_WIN
- negative = META_LOSS

TIMEOUT is excluded from binary training/evaluation and its score distribution
is reported separately.

## Population split

The full 2,175 chronological population is partitioned before removing
TIMEOUT:

- first 45%: inner train
- next 15%: inner validation
- next 20%: outer validation
- final 20%: untouched final test

Resolved counts:

- inner train: 856
- inner validation: 297
- outer train: 1,153
- outer validation: 364
- dev+validation refit pool: 1,517
- final test: 374

## Architectures

Three otherwise comparable logistic architectures are tested:

1. BASELINE_UNPURGED_UNWEIGHTED
2. PURGED_UNWEIGHTED
3. PURGED_UNIQUENESS_WEIGHTED

## Purge + embargo rule

For a holdout block, a training event is removed if:

- its Stage 3A label interval reaches the first holdout timestamp; or
- it opened during the 30 minutes immediately before holdout start.

This applies only to the purged architectures.

## Uniqueness weighting

The weighted architecture uses Stage 3A event uniqueness weights.

Weights are normalized to mean 1 inside each training sample before fitting.

No class-balance weight is added, so the comparison isolates the effect of
outcome-window uniqueness.

## Feature policy

Only causal pre-entry feature columns are eligible.

Excluded structurally:

- time-of-day fields;
- latency features;
- raw absolute scale proxies;
- constant features in training.

Portable feature count: 207.

Feature ranking is performed on the relevant training partition only.

## Model selection

Within each architecture, hyperparameters are selected on inner validation:

- top-k features: 5 / 10 / 20 / 40 / 60 / 80
- L2: 0.1 / 1.0 / 4.0

Selection order:

1. average precision;
2. AUC;
3. top-10% precision;
4. smaller feature count.

Each selected architecture is then refit on the outer training window and
evaluated on outer validation.

Architecture selection order:

1. outer-validation average precision;
2. outer-validation AUC;
3. outer-validation top-10% precision.

Only after the architecture is selected is the final 20% test evaluated.

## Reproducibility

Code:

- research/wrong_direction/wd5h_stage3b.py
- research/wrong_direction/scripts/wd5h_stage3b.py
- research/wrong_direction/tests/test_wd5h_stage3b.py

Frozen outputs:

- /opt/core-app/data/wd5h3b_meta_model_predictions.csv
- /opt/core-app/data/wd5h3b_meta_model_results.json
