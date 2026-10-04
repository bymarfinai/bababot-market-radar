# SD-2A — SHORT Archetype-Specific Multi-Feature Combinations

Status: **NO PASS / T0 MULTI-FEATURE HOLDOUT FAILURE**

## Frozen scope

Research-only matched lanes from SD-1C / SD-1D:

### Lane 0
Provisional `SHORT_ARCHETYPE_0` WIN vs frozen `SHORT_LOSS_CLUSTER_0`

- Discovery: **17 WIN / 82 LOSS**
- Validation: **8 WIN / 24 LOSS**
- Reserve: **5 WIN / 17 LOSS**

### Lane 1
Provisional `SHORT_ARCHETYPE_1` WIN vs frozen `SHORT_LOSS_CLUSTER_1`

- Discovery: **42 WIN / 213 LOSS**
- Validation: **19 WIN / 66 LOSS**
- Reserve: **8 WIN / 90 LOSS**

Because SD-1C winner clustering missed its preregistered bootstrap-ARI gate, both lanes remain research classes only.

## Search design

Per lane:

- T0 numeric feature family frozen from SD-1B
- Discovery-only feature ranking
- greedy de-correlation at |r| <= **0.85**
- exactly **18 features** frozen per lane
- every 2-, 3-, and 4-feature subset
- class-weighted L2 logistic regression
- `C = {0.01, 0.1, 1, 10, 100}`
- fit on Discovery only
- model/subset selected using Discovery + Validation only
- Reserve opened only after model freeze

Search volume:

- 4,029 subsets/lane
- 20,145 fits/lane
- **40,290 model fits total**

No Reserve result participated in feature-pool construction, subset selection, regularization selection, coefficient selection, or model ranking.

---

# Lane 0 — Flow-gap / Counterflow research lane

## Single-feature reference from SD-1D

`f_f_market_dispersion_15m`

- Discovery AUC: **0.711**
- Validation AUC: **0.708**
- Reserve AUC: **0.441**

## Best 2-feature model frozen from D+V

Features:
- `f_f_market_dispersion_15m`
- `f_gate_impulse_concentration_ratio`

C = **0.01**

AUC:
- Discovery: **0.780**
- Validation: **0.745**
- Reserve: **0.294**

The 2-feature combination improved D/V but failed severely on the sealed holdout.

## Best 3-feature model

Features:
- `f_f_market_dispersion_15m`
- `f_gate_impulse_concentration_ratio`
- `f_f_taker_selected_share_3m`

C = **0.01**

AUC:
- Discovery: **0.824**
- Validation: **0.802**
- Reserve: **0.447**

Coefficients:
- market dispersion 15m: **+0.150**
- impulse concentration: **-0.095**
- selected taker share 3m: **-0.069**

## Best 4-feature model

Adds:
- `f_context_regime_ema20`

AUC:
- Discovery: **0.833**
- Validation: **0.802**
- Reserve: **0.447**

The 3- and 4-feature models tied on the D/V selection floor. The preregistered fewer-feature tie-break therefore freezes the **3-feature model**.

## Frozen Lane 0 model

> **D/V/R AUC = 0.824 / 0.802 / 0.447**

Status:

> **WEAK_FAIL**

This is a classic holdout failure. D/V separation looks excellent, but Reserve is below random ranking.

### Feature-shift anatomy

The frozen model learned:

1. higher market dispersion → more winner-like;
2. lower impulse concentration → more winner-like;
3. lower selected taker share 3m → more winner-like.

Observed medians:

| Feature | D WIN | D LOSS | V WIN | V LOSS | R WIN | R LOSS |
|---|---:|---:|---:|---:|---:|---:|
| market dispersion 15m | .126 | .089 | .140 | .078 | **.040** | **.040** |
| impulse concentration | .183 | .238 | .103 | .210 | **.296** | **.172** |
| taker share 3m | .558 | .604 | .607 | .623 | .667 | .717 |

Two important shifts occur in Reserve:

- market-dispersion separation almost disappears;
- impulse-concentration direction **reverses**.

The taker-share relation remains directionally consistent, but cannot rescue the combined score.

Score medians:
- Discovery WIN / LOSS: **0.528 / 0.484**
- Validation: **0.512 / 0.481**
- Reserve: **0.454 / 0.456**

So the model loses ranking separation in Reserve.

Discovery-frozen score quintiles also show calibration shift: all 22 Reserve observations fall into only the first two Discovery quintile ranges; none reach Discovery Q3-Q5.

---

# Lane 1 — Flow-aligned / Recovery research lane

## Single-feature reference from SD-1D

`f_median_abs_ret_5m_pct`

- Discovery AUC: **0.622**
- Validation AUC: **0.724**
- Reserve AUC: **0.450**

## Best 2-feature model

Features:
- `f_f_selected_slope5_norm`
- `f_new_extension_5m_norm`

C = **0.01**

AUC:
- Discovery: **0.672**
- Validation: **0.711**
- Reserve: **0.403**

## Best 3-feature model

Features:
- `f_f_market_selected_ret_1m`
- `f_micro_decay_5_vs_prev5`
- `f_new_extension_5m_norm`

C = **0.01**

AUC:
- Discovery: **0.712**
- Validation: **0.697**
- Reserve: **0.389**

## Best 4-feature model / frozen overall

Features:
- `f_f_market_selected_ret_1m`
- `f_micro_decay_5_vs_prev5`
- `f_micro_range_contraction_after_impulse`
- `f_new_extension_5m_norm`

C = **10**

AUC:
- Discovery: **0.720**
- Validation: **0.717**
- Reserve: **0.426**

Coefficients:
- selected market return 1m: **-0.681**
- micro decay 5 vs prev5: **-0.448**
- range contraction after impulse: **-0.278**
- extension 5m norm: **-0.502**

## Frozen Lane 1 model

> **D/V/R AUC = 0.720 / 0.717 / 0.426**

Status:

> **WEAK_FAIL**

Again the D/V combination looks useful and then fails Reserve.

### Feature-shift anatomy

| Feature | D WIN | D LOSS | V WIN | V LOSS | R WIN | R LOSS |
|---|---:|---:|---:|---:|---:|---:|
| market selected ret 1m | -.005 | .019 | .024 | .018 | .015 | .010 |
| micro decay 5/prev5 | -.757 | -.557 | -.599 | -.649 | **-.566** | **-.772** |
| range contraction | .288 | .750 | .571 | 1.068 | **.271** | **.710** |
| extension 5m norm | 4.347 | 4.486 | 3.647 | 4.406 | **5.526** | **5.195** |

Only the range-contraction relationship remains strongly direction-consistent into Reserve.

Several other relationships flatten or reverse.

Score medians:
- Discovery WIN / LOSS: **0.554 / 0.424**
- Validation: **0.533 / 0.415**
- Reserve: **0.393 / 0.443**

The score ranking therefore reverses in the sealed holdout.

Most strikingly, using the Discovery-frozen score quintile boundaries:

- Reserve Q5 contains **9 trades**
- strong winners in Reserve Q5: **0**
- Reserve Q4 contains **16 trades**
- strong winners in Reserve Q4: **0**

So the model's highest-confidence region did not transport.

---

# Multi-feature improvement vs single-feature

| Lane | Single D/V floor | Multi D/V floor | Improvement | Single R | Multi R |
|---|---:|---:|---:|---:|---:|
| Lane 0 | .708 | **.802** | **+.094** | .441 | .447 |
| Lane 1 | .622 | **.717** | **+.095** | .450 | .426 |

This is the key result.

Multi-feature modeling clearly finds stronger structure in Discovery + Validation.

But:

> **none of that improvement transports to Reserve.**

Lane 0 Reserve remains around random.
Lane 1 Reserve becomes worse.

---

# Interpretation

SD-2A confirms three things.

## 1. T0 interactions exist

The strong D/V gains show that SHORT winner-vs-failure structure is not purely one-dimensional.

This validates the conditional-signal insight from SD-1C / SD-1D.

## 2. The discovered interactions are not stationary enough

The sealed Reserve does not merely weaken the models; it reverses their ranking.

This points to some combination of:
- temporal regime shift;
- unstable T0 feature-target relationships;
- small winner support, especially Lane 0;
- provisional winner-cluster instability from SD-1C;
- multiple-comparison selection pressure despite a sealed Reserve.

The Reserve did its job: it prevented an apparently excellent D/V model from being promoted.

## 3. More T0 combination search is not justified

The search already tested **40,290** logistic combinations under the frozen 18-feature pools.

Blindly increasing:
- feature count,
- regularization grid,
- polynomial interactions,
- thresholds,
- or model complexity

would increase overfit risk rather than address the observed holdout shift.

---

# Decision

## Lane 0
**WEAK_FAIL**
- frozen D/V/R = **0.824 / 0.802 / 0.447**

## Lane 1
**WEAK_FAIL**
- frozen D/V/R = **0.720 / 0.717 / 0.426**

## Overall SD-2A

> **NO PASS — T0 MULTI-FEATURE COMBINATIONS DO NOT SURVIVE RESERVE**

No model, coefficient set, score, threshold, veto, or feature combination receives entry authority.

Paper / production runtime remains unchanged.

---

# Recommended next research

The playbook says that when a lane cannot be solved reliably at T0, research should move into **temporal confirmation** rather than continue tuning static entry features.

However, because both lanes show explicit Reserve relationship shift, the clean next step should first preserve this failure anatomy and then test causal trajectory features at:

- T+1
- T+2
- T+3

with strict outcome censoring.

The key question becomes:

> **Does post-signal trajectory restore stable winner-vs-failure separation when static T0 relationships drift across time?**
