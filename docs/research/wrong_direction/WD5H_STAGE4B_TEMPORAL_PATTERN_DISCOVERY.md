# WD-5H Stage 4B — Temporal Confirmation Pattern Discovery

Status: EXECUTED ON VPS core-prod
Authority: RESEARCH ONLY
Production behavior changed: NO

## Goal

Determine whether the causal T+1 / T+2 / T+3 feature evolution reconstructed
in Stage 4A separates future META_WIN from META_LOSS more strongly than the
static T0 snapshot.

Stage 4B does not choose a TAKE threshold.

## Critical survivor guard

A first raw audit showed very strong temporal separation. Before accepting
that result, Stage 4B checks whether a trade's Stage 3A barrier outcome had
already resolved before the confirmation timestamp.

For each horizon, any META_WIN or META_LOSS with:

label_end_ms <= T0 + horizon

is excluded from the discrimination audit at that horizon.

This prevents a temporal feature from reading an outcome that is already
known by that timestamp.

All formal Stage 4B results use this survivor guard.

## Chronological robustness

The 2,175 chronological candidates remain split:

- first 60% train
- next 20% validation
- final 20% test

TIMEOUT is excluded from WIN-vs-LOSS discrimination.

A univariate feature is considered direction-stable only when its AUC
direction agrees in all three chronological partitions.

Separation is:

2 * abs(AUC - 0.5)

Descriptive tiers:

- robust: stable direction and minimum split separation >= 0.05
- strong: stable direction and minimum split separation >= 0.10

These tiers are discovery descriptors, not production thresholds.

## Diagnostic multivariate model

For each horizon a fixed logistic diagnostic is trained:

- temporal features only;
- top 12 ranked on training separation only;
- L2 = 1.0;
- no threshold selection;
- no hyperparameter search.

This model is used only to compare ranking strength across horizons.

## Families

Stage 4B audits:

- direct confirmation path;
- microstructure/path;
- market-relative movement;
- taker/flow;
- delta versus T0;
- OI-derived context;
- other structure features.

Historical fresh OI coverage is almost absent inside three minutes, so OI is
not interpreted as fresh temporal evidence.

## Reproducibility

Code:

- research/wrong_direction/wd5h_stage4b.py
- research/wrong_direction/scripts/wd5h_stage4b.py
- research/wrong_direction/tests/test_wd5h_stage4b.py

Frozen outputs:

- /opt/core-app/data/wd5h4b_temporal_pattern_results.json
- /opt/core-app/data/wd5h4b_feature_audit.csv
