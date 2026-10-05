# SHORT-S8 — Unified Full-Universe Replay Contract

Status: **PREREGISTERED / RESEARCH ONLY / RESERVE SEALED FOR ROUTER EVALUATION**

## Purpose

Replicate LONG Stage 3C.5 on the frozen SHORT universe.

The output must be the first unified SHORT funnel:

> **655 candidates → OPEN → strong WIN captured / 99 → non-target → profitable non-target → realized-positive → historical PnL / peak-MFE opportunity**

No new SHORT discovery logic is introduced here.

## Frozen universe

Source:
- `research/short_detector/results/sd1a_short_universe_655.csv`

Resolved SHORT candidates:
- total: **655**
- strong WIN target: **99**
- non-target: **556**
  - weak META_WIN: 64
  - META_LOSS: 492

Chronological split:
- Discovery: 393
- Validation: 131
- Reserve: 131

Strong WIN:
- Discovery: 59
- Validation: 27
- Reserve: 13

## Frozen anatomy labels for outcome-blind router

Winner anatomy:
- `research/short_detector/results/sd1c_strong_winner_assignments.csv`

Loss anatomy:
- `research/short_detector/results/sd1d_loss_cluster_assignments.csv`

Router-labeled rows:
- total: **591**
- Discovery: 354
- Validation: 117
- Reserve: 120

Lane labels:
- lane 0 = winner archetype 0 + matched loss cluster 0
- lane 1 = winner archetype 1 + matched loss cluster 1

Weak META_WIN rows have no anatomy label and are excluded from router fitting/evaluation, but the frozen router is applied to them at unified inference.

## Outcome-blind T0 router

Replicate LONG Stage 3C.5 methodology without tuning.

Fit only on Discovery router-labeled rows.

Frozen feature family:

1. `f_gate_flow_family`
2. `f_gate_taker_share_for_selected`
3. `f_gate_side_ret_1m_pct`
4. `f_new_flow_support`
5. `f_new_micro_accel_1_vs_3`
6. `f_f_coin_minus_market_30m`
7. `f_f_oi_change_30m_pct`
8. `f_micro_volume_ratio_last_vs_prev10`

Preprocessing:
- categorical `f_gate_flow_family`: Discovery one-hot, unknown all-zero
- numeric fields: Discovery median imputation
- numeric StandardScaler fit on Discovery only

Model:
- logistic regression
- L2 penalty
- C = **0.1**
- solver = liblinear
- class_weight = balanced
- random_state = 4104
- probability >= 0.50 → lane 1
- otherwise lane 0

No hyperparameter, feature, threshold, or class definition is tuned using Validation or Reserve.

Required router report:
- D/V/R AUC
- D/V/R accuracy
- confusion matrix
- predicted lane proportions across all 655

## Frozen lane policies

### Lane 0

Current accepted state:

> **NO_ACCEPTED_SELECTOR**

Reason:
- SD-2A static multi-feature models failed sealed Reserve
- SD-2B2 D/V-selected primary temporal rules failed Reserve
- post-hoc alternative Lane-0 rules are not eligible for promotion

Therefore in SHORT-S8:

> routed lane 0 → **NO OPEN**

This is intentional. SHORT-S9 missed-winner anatomy will quantify the cost and classify the missed Lane-0 winners.

### Lane 1

Frozen SD-2B2 rule:

> causal unresolved T+3 snapshot AND
> `t3_confirm_side_return_pct >= +0.0338983050847%`

Eligibility:
- `primary_label_end_ms > t3_target_ms`
- T+3 snapshot present

No early T+1/T+2 recovery is allowed in S8.
That belongs to SHORT-S10, exactly like LONG Stage 3C.7A.

## Unified replay

Apply the router to all 655 candidates using T0 only.

Then:
- routed lane 0: NO OPEN
- routed lane 1: apply frozen T+3 causal rule

No eventual WIN/LOSS label is used for routing or selection.

## Required metrics

Overall:
- candidates
- OPEN
- strong WIN captured / 99
- recall
- non-target selected
- precision
- baseline strong-target prevalence
- precision lift
- weak META_WIN selected
- META_LOSS selected
- profitable non-target count
- realized-positive selected count
- historical WR
- historical original-entry PnL
- average historical return/trade
- peak-MFE equivalent

By split D/V/R:
- OPEN
- strong WIN captured / split strong WIN
- recall
- precision
- lift
- historical PnL

By routed lane:
- candidate count
- OPEN
- strong WIN captured
- non-target selected

Opportunity anatomy:
- strong-target peak-MFE equivalent
- non-target peak-MFE equivalent
- historical realized PnL by target/non-target

## Integrity

- This is the SHORT equivalent of LONG Stage 3C.5 / SHORT-S8.
- No entry threshold tuning.
- No early same-threshold recovery.
- No missed-winner recovery.
- No exit/profit-protector integration.
- No paper/live promotion.
- Historical PnL is reference-only because temporal Lane-1 entries are delayed in execution-realistic use.
- Paper trading remains PAUSE_ENTRIES.