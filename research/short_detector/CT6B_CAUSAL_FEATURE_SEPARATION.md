# SHORT-CT6B — Causal Feature Separation for Low-MFE Failure

Status: **PASS feature-separation / T2 is the strongest first detector lane**

## Objective

CT-6B asks whether future low-MFE failures can be distinguished from real opportunities using only information that already exists at the lane decision time.

Research labels:

- **BAD-A**: future max MFE < 0.30%
- **BAD-B**: 0.30% <= future max MFE < 0.50%
- **GRAY**: 0.50% <= future max MFE < 1.00%
- **TARGET-MFE**: future max MFE >= 1.00%

Binary separation uses BAD = MFE <0.50% versus TARGET = MFE >=1.00%. GRAY is excluded from binary AUC.

MFE remains a research label only.

## Causality contract

Allowed information depends on lane:

- T0: base/pre-entry features only
- T1: base + T1 snapshots
- T2: base + T1 + T2 snapshots
- T3: base + T1 + T2 + T3 snapshots

Observed values such as t2_confirm_mfe_pct are allowed because they are already known at T2. The forbidden feature is future max MFE itself.

Derived progression variables are also causal, for example d2_confirm_mfe_pct = t2_confirm_mfe_pct - t1_confirm_mfe_pct.

No runtime or paper rule is changed in CT-6B.

## Stability definition

A feature is stable only if:

- binary coverage >=95%
- overall AUC separation >=0.58
- Research and Fresh point in the same BAD direction
- at least 5 chronological blocks point in the same direction

AUC >0.50 means larger values associate with BAD. AUC <0.50 means smaller values associate with BAD. Separation = max(AUC, 1-AUC).

This stage ranks features only. It does not choose production thresholds.

## Headline

| Lane | BAD | TARGET | Stable causal separators |
|---|---:|---:|---:|
| T0 | 112 | 89 | 5 |
| T1 | 92 | 73 | 10 |
| **T2** | **127** | **118** | **9** |
| T3 | 67 | 46 | 11 |

T2 remains the highest-priority lane because it combines the largest low-MFE loss mass from CT-6A, balanced BAD/TARGET sample size, strong temporal features, and several features with 6/6 chronological consistency.

## T0 — pre-entry separation is real but weaker

| Feature | BAD direction | Separation | Research AUC | Fresh AUC | Blocks |
|---|---|---:|---:|---:|---:|
| f_f_coin_minus_market_30m | LOW | **0.646** | 0.434 | 0.313 | 5/6 |
| f_gate_side_ret_1m_pct | LOW | **0.637** | 0.426 | 0.329 | 5/6 |
| f_new_micro_accel_1_vs_3 | LOW | 0.603 | 0.405 | 0.395 | 5/6 |
| f_new_momentum_curvature | LOW | 0.599 | 0.389 | 0.403 | 5/6 |
| f_f_oi_change_30m_pct | HIGH | 0.591 | 0.601 | 0.585 | 5/6 |

BAD T0 candidates generally show weaker coin-vs-market relative move, weaker 1m side return, weaker micro acceleration, weaker momentum curvature, and somewhat higher OI change.

Example medians for f_f_coin_minus_market_30m: BAD-A 0.762, BAD-B 0.778, TARGET 1.485.

Example medians for f_gate_side_ret_1m_pct: BAD-A 0.145, BAD-B 0.219, TARGET 0.324.

T0 likely requires a multi-feature detector; a single raw threshold is unlikely to be safe enough.

## T1 — early observed excursion becomes informative

| Feature | BAD direction | Separation | BAD-A AUC | BAD-B AUC | R/F | Blocks |
|---|---|---:|---:|---:|---|---:|
| t1_confirm_mfe_pct | LOW | **0.727** | 0.228 | 0.326 | 0.246 / 0.286 | 5/6 |
| t1_confirm_side_return_pct | LOW | **0.700** | 0.276 | 0.328 | 0.221 / 0.329 | 5/6 |
| t1_f_micro_decay_3_vs_prev3 | HIGH | 0.633 | 0.646 | 0.616 | 0.655 / 0.616 | 5/6 |
| f_f_coin_minus_market_30m | LOW | 0.625 | 0.386 | 0.362 | 0.417 / 0.373 | 5/6 |
| t1_confirm_last_clv_selected | HIGH | 0.608 | 0.642 | 0.568 | 0.581 / 0.624 | 5/6 |
| t1_delta_f_coin_minus_market_15m | LOW | 0.608 | 0.365 | 0.425 | 0.310 / 0.378 | 5/6 |

Observed T1 MFE medians: BAD-A 0.162%, BAD-B 0.237%, GRAY 0.292%, TARGET 0.346%.

The very poor trades already begin to reveal themselves at T1, but BAD-B still overlaps TARGET materially.

## T2 — strongest first detector target

| Feature | BAD direction | Separation | BAD-A AUC | BAD-B AUC | Research / Fresh | Blocks |
|---|---|---:|---:|---:|---|---:|
| **t2_confirm_mfe_pct** | LOW | **0.721** | 0.217 | 0.364 | **0.279 / 0.282** | **6/6** |
| **t2_confirm_side_return_pct** | LOW | **0.710** | 0.249 | 0.345 | 0.362 / 0.260 | **6/6** |
| **d2_confirm_mfe_pct** | LOW | **0.708** | 0.254 | 0.343 | **0.278 / 0.303** | **6/6** |
| f_f_coin_minus_market_30m | LOW | 0.644 | 0.326 | 0.397 | 0.458 / 0.319 | 5/6 |
| t2_delta_micro_selected_vwap_extension_20 | LOW | 0.632 | 0.342 | 0.402 | 0.384 / 0.366 | **6/6** |
| d2_confirm_side_return_pct | LOW | 0.626 | 0.337 | 0.424 | 0.420 / 0.353 | **6/6** |
| d2_confirm_trades | LOW | 0.623 | 0.345 | 0.421 | 0.305 / 0.411 | 5/6 |
| t2_confirm_trades | LOW | 0.599 | 0.364 | 0.451 | 0.351 / 0.425 | 5/6 |

### Most important T2 feature: observed MFE

Median t2_confirm_mfe_pct:

- BAD-A: **0.156%**
- BAD-B: **0.240%**
- GRAY: 0.336%
- TARGET: **0.339%**

Research/Fresh AUCs are almost identical: 0.279 and 0.282, with 6/6 blocks in the same direction.

### T2 side return

Median:

- BAD-A: **0.090%**
- BAD-B: **0.120%**
- TARGET: **0.210%**

Again 6/6 blocks point in the same direction.

### T1 -> T2 MFE growth

Median d2_confirm_mfe_pct:

- BAD-A: **+0.017 pp**
- BAD-B: **+0.048 pp**
- GRAY: +0.084 pp
- TARGET: **+0.164 pp**

The detector is therefore not only seeing low excursion at T2. BAD trades also fail to build favorable excursion between T1 and T2.

This gives CT-6C a natural multi-feature hypothesis: low absolute observed MFE, weak T2 side confirmation, weak T1-to-T2 MFE growth, and optionally weak relative-market/microstructure support.

## T3 — strong separation, but late

| Feature | BAD direction | Separation | R/F | Blocks |
|---|---|---:|---|---:|
| t3_confirm_mfe_pct | LOW | **0.776** | 0.410 / 0.135 | 5/6 |
| t2_confirm_mfe_pct | LOW | **0.744** | 0.338 / 0.210 | **6/6** |
| t3_confirm_trades | LOW | 0.666 | 0.395 / 0.296 | **6/6** |
| d3_confirm_trades | LOW | 0.660 | 0.477 / 0.274 | 5/6 |
| f_f_coin_minus_market_30m | LOW | 0.654 | 0.383 / 0.327 | 5/6 |
| d2_confirm_trades | LOW | 0.650 | 0.410 / 0.318 | **6/6** |
| t1_confirm_mfe_pct | LOW | 0.644 | 0.361 / 0.350 | **6/6** |
| t2_confirm_trades | LOW | 0.641 | 0.393 / 0.335 | **6/6** |

Median t3_confirm_mfe_pct: BAD-A 0.157%, BAD-B 0.157%, TARGET 0.323%.

T3 has strong information, but it is late and CT-5B already addresses a subset of T3 rescue failures. Some T3 effects are also much stronger in Fresh than Research, so pooled thresholds would be risky.

## BAD-A versus BAD-B

Across T1/T2, observed-excursion features separate BAD-A much more strongly than BAD-B.

For T2 observed MFE:

- BAD-A vs TARGET AUC: 0.217, separation 0.783
- BAD-B vs TARGET AUC: 0.364, separation 0.636

Therefore the safe engineering sequence is to catch the obviously dead BAD-A trades first, then expand toward BAD-B only when TARGET retention remains stable.

## CT-6B verdict

> **PASS feature separation.**

There is enough causal signal to justify a low-MFE failure detector.

T0 has useful but moderate pre-entry separation. T1 improves materially once early excursion is observed. T2 is the best first detector lane. T3 has the strongest raw information but is late and partially overlaps CT-5B.

## Frozen CT-6C input hypothesis

CT-6C should begin with **T2 only**, not all lanes simultaneously.

Primary T2 causal family:

1. t2_confirm_mfe_pct
2. t2_confirm_side_return_pct
3. d2_confirm_mfe_pct
4. t2_delta_micro_selected_vwap_extension_20
5. d2_confirm_side_return_pct
6. f_f_coin_minus_market_30m

Secondary/support:

- d2_confirm_trades
- t2_confirm_trades

CT-6C should search high-precision BAD vetoes, starting with BAD-A.

Required reporting:

- BAD-A rejection
- BAD-B rejection
- TARGET-MFE retention
- strong retention
- Research / Fresh separately
- all six chronological blocks
- realized protected PnL of vetoed cohort

CT-6C must not use future max MFE, realized PnL, future close reason, or profit-protector outcome as detector inputs.

No production promotion is authorized by CT-6B.