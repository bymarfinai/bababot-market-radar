# SD-2B1 — SHORT Temporal Anatomy Contract

Status: **PREREGISTERED / ANATOMY ONLY / NO THRESHOLD TUNING**

## Purpose
Measure whether causal post-signal trajectory at T+1 / T+2 / T+3 separates matched SHORT winners from matched SHORT failures more consistently than static T0.

This stage is descriptive anatomy only.
It does **not** tune an entry threshold, classifier, or production rule.

## Frozen matched research lanes

### Lane 0
- provisional winner `SHORT_ARCHETYPE_0`
- frozen failure `SHORT_LOSS_CLUSTER_0`

Frozen population before causal censoring:
- Discovery: 17 WIN / 82 LOSS
- Validation: 8 WIN / 24 LOSS
- Reserve: 5 WIN / 17 LOSS

### Lane 1
- provisional winner `SHORT_ARCHETYPE_1`
- frozen failure `SHORT_LOSS_CLUSTER_1`

Frozen population before causal censoring:
- Discovery: 42 WIN / 213 LOSS
- Validation: 19 WIN / 66 LOSS
- Reserve: 8 WIN / 90 LOSS

Sources:
- `research/short_detector/results/sd1a_short_universe_655.csv`
- `research/short_detector/results/sd1c_strong_winner_assignments.csv`
- `research/short_detector/results/sd1d_loss_cluster_assignments.csv`
- temporal features: `/opt/core-app/data/wd5h4a_temporal_features.csv`

## Causal eligibility

At horizon T+N, a row is eligible only when:

`primary_label_end_ms > tN_target_ms`

and the temporal snapshot is present.

Rows whose primary outcome has already resolved are excluded from that horizon.

## Horizons

Analyze:
- T+1
- T+2
- T+3

No later horizon is introduced in SD-2B1.

## Predeclared canonical temporal observables

Predictor-anatomy fields:

1. `confirm_side_return_pct`
2. `confirm_selected_taker_share`
3. `f_micro_side_ret_1m`
4. `f_micro_side_ret_3m`
5. `f_micro_side_ret_5m`
6. `f_micro_selected_taker_share_1m`
7. `f_micro_selected_taker_share_3m`
8. `f_micro_selected_vwap_extension_20`
9. `f_micro_reversal_pressure`
10. `f_f_market_dispersion_15m`
11. `f_f_coin_minus_market_15m`
12. `f_f_coin_residual_5m_vs_btc`
13. `f_f_taker_selected_share_3m`
14. `f_f_selected_slope5_norm`
15. `delta_micro_side_ret_1m`
16. `delta_micro_side_ret_3m`
17. `delta_micro_selected_taker_share_3m`
18. `delta_micro_selected_vwap_extension_20`
19. `delta_f_coin_minus_market_15m`
20. `delta_f_coin_residual_5m_vs_btc`

The horizon prefix (`t1_`, `t2_`, `t3_`) is applied mechanically.

## Outcome-linked anatomy fields

These are reported descriptively but **excluded from predictor ranking** because they overlap the strong-WIN target definition or are directly path-outcome related:

- `confirm_mfe_pct`
- `confirm_mae_pct`

## Required outputs

For each lane × horizon × split:
- causal eligible WIN / LOSS counts;
- causal coverage relative to the frozen lane population;
- medians of side return, MFE, MAE, taker share;
- historical WD1 outcome mix among surviving failures;
- median canonical predictor by WIN / LOSS;
- raw ROC AUC and separation AUC for each canonical predictor;
- same-direction stability across D/V/R;
- D/V floor and D/V/R floor as anatomy diagnostics only.

For each lane:
- earliest horizon with at least one canonical predictor whose **same frozen direction** has D/V/R AUC >=0.60;
- strongest all-split canonical trajectory feature;
- whether temporal separation improves versus SD-2A frozen T0 Reserve result.

## Integrity

- No threshold tuning.
- No multi-feature fitting.
- No feature search outside the 20 predeclared canonical observables.
- No Reserve-based feature direction selection:
  - useful direction is frozen from Discovery only.
- Reserve may only evaluate the Discovery-frozen direction.
- No runtime / paper / production changes.
- Paper trading entry pause remains independent.