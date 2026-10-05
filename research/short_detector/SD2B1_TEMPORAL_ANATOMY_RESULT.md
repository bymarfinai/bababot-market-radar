# SD-2B1 — SHORT Temporal Anatomy

Status: **PASS_DIAGNOSTIC — temporal signal found / no threshold authority**

## Frozen scope

Matched research lanes from SD-1C / SD-1D:

### Lane 0
- provisional winner `SHORT_ARCHETYPE_0`
- frozen failure `SHORT_LOSS_CLUSTER_0`
- frozen population before censoring:
  - Discovery 17 WIN / 82 LOSS
  - Validation 8 WIN / 24 LOSS
  - Reserve 5 WIN / 17 LOSS

### Lane 1
- provisional winner `SHORT_ARCHETYPE_1`
- frozen failure `SHORT_LOSS_CLUSTER_1`
- frozen population before censoring:
  - Discovery 42 WIN / 213 LOSS
  - Validation 19 WIN / 66 LOSS
  - Reserve 8 WIN / 90 LOSS

Temporal horizons:
- T+1
- T+2
- T+3

Causal eligibility:
`primary_label_end_ms > temporal_target_ms`

Rows already resolved before a temporal decision point are excluded.

`confirm_mfe_pct` and `confirm_mae_pct` are reported only as anatomy and are excluded from predictor ranking.

---

# 1. Causal coverage

## Lane 0

| Horizon | Discovery | Validation | Reserve |
|---|---:|---:|---:|
| T+1 | 85 = 16W/69L | 29 = 7W/22L | 19 = 5W/14L |
| T+2 | 67 = 12W/55L | 28 = 7W/21L | 17 = 4W/13L |
| T+3 | 55 = 9W/46L | 22 = 7W/15L | 15 = 4W/11L |

Coverage declines with delay, especially in Discovery.

Reserve winner support is small:
- T+1: 5
- T+2: 4
- T+3: 4

Therefore very high Reserve AUCs in Lane 0 must be treated as low-support anatomy rather than final proof.

## Lane 1

| Horizon | Discovery | Validation | Reserve |
|---|---:|---:|---:|
| T+1 | 241 = 38W/203L | 83 = 18W/65L | 90 = 6W/84L |
| T+2 | 219 = 35W/184L | 76 = 17W/59L | 85 = 6W/79L |
| T+3 | 181 = 27W/154L | 72 = 17W/55L | 78 = 6W/72L |

Lane 1 has materially larger causal support and remains suitable for T+3 confirmation research.

---

# 2. Primary trajectory anatomy

## Lane 0

### T+1
Median side return:
- D WIN: **+0.132%**
- D LOSS: ~0.000%
- V WIN: ~0.000%
- V LOSS: **-0.056%**
- R WIN: **+0.236%**
- R LOSS: **-0.038%**

Median MFE at T+1:
- D WIN / LOSS: **0.259% / 0.160%**
- V: **0.130% / 0.132%**
- R: **0.419% / 0.125%**

### T+2
Median side return:
- D WIN / LOSS: **+0.045% / ~0.000%**
- V: **+0.011% / -0.040%**
- R: **+0.461% / +0.027%**

### T+3
Median side return:
- D WIN / LOSS: **+0.100% / -0.047%**
- V: **+0.056% / +0.010%**
- R: **+0.522% / ~0.000%**

Lane 0 winners increasingly show favorable side-relative development after the signal, but split-to-split magnitude varies materially.

## Lane 1

### T+1
Median side return:
- D WIN / LOSS: ~0.000% / -0.003%
- V: **+0.077% / -0.028%**
- R: **+0.053% / -0.022%**

### T+2
Median side return:
- D WIN / LOSS: **+0.104% / ~0.000%**
- V: ~0.000% / **-0.038%**
- R: **+0.111% / ~0.000%**

### T+3
Median side return:
- D WIN / LOSS: **+0.158% / -0.035%**
- V: **+0.111% / -0.082%**
- R: **+0.168% / -0.026%**

This is much more coherent than static T0:
the same directional relationship appears across Discovery, Validation, and Reserve by T+3.

---

# 3. Canonical temporal feature stability

20 temporal observables were predeclared before analysis.
Useful direction was frozen from Discovery only.
Validation and Reserve evaluated that same direction.

## Lane 0

### T+1
Only **1 / 20** canonical feature keeps AUC >=0.60 in all three splits.

Best:
`delta_f_coin_minus_market_15m` — HIGH favors WIN

AUC D / V / R:
> **0.668 / 0.669 / 0.814**

D/V/R floor:
> **0.668**

This is the earliest stable Lane-0 temporal signal.

### T+2
**6 / 20** canonical features keep all-split AUC >=0.60.

Best:
`delta_f_coin_minus_market_15m`

AUC:
> **0.679 / 0.735 / 0.885**

D/V/R floor:
> **0.679**

Other all-split-stable examples:
- selected slope5 norm: **0.653 / 0.687 / 0.692**
- confirm side return: **0.646 / 0.653 / 1.000**
- delta VWAP extension: **0.644 / 0.701 / 0.750**
- delta coin residual vs BTC: **0.635 / 0.673 / 0.692**

### T+3
**5 / 20** canonical features keep all-split AUC >=0.60.

Best:
`delta_micro_selected_vwap_extension_20`

AUC:
> **0.671 / 0.676 / 0.977**

Other stable examples:
- micro side return 3m: **0.783 / 0.657 / 0.977**
- micro side return 5m: **0.691 / 0.610 / 0.636**

Interpretation:
Lane 0 already contains useful temporal differentiation at T+1, with the broadest feature support appearing at T+2.

Because Reserve contains only 4–5 causal winners, SD-2B1 does **not** promote Lane 0 based on the very high Reserve AUC values.

---

# 4. Lane 1 temporal stability

## T+1
No canonical feature keeps AUC >=0.60 across D/V/R.

Best:
`confirm_side_return_pct`

AUC:
> **0.588 / 0.689 / 0.663**

D/V/R floor:
> **0.588**

Verdict:
T+1 is not yet sufficiently separated.

## T+2
Exactly **1 / 20** canonical feature keeps AUC >=0.60 across all splits:

`confirm_side_return_pct` — HIGH favors WIN

AUC:
> **0.706 / 0.627 / 0.852**

D/V/R floor:
> **0.627**

This is the earliest all-split >=0.60 Lane-1 signal.

## T+3
Temporal structure becomes materially stronger.

**9 / 20** canonical features maintain AUC >=0.60 across D/V/R.
**4** maintain an all-split floor >=0.65.

Best:

`confirm_side_return_pct`

AUC:
> **0.779 / 0.725 / 0.843**

D/V/R floor:
> **0.725**

Other stable T+3 features:

- micro side return 3m: **0.735 / 0.698 / 0.785**
- selected slope5 norm: **0.671 / 0.680 / 0.701**
- delta VWAP extension: **0.758 / 0.651 / 0.755**
- selected VWAP extension: **0.696 / 0.634 / 0.653**

This is the strongest SD-2B1 result.

> **Lane 1 T+3 side return transports across Discovery, Validation, and sealed Reserve, unlike the static T0 models from SD-2A.**

---

# 5. Direct comparison with SD-2A T0 failure

SD-2A frozen static models:

### Lane 0
T0 multi-feature:
> **0.824 / 0.802 / 0.447**

Best temporal all-split anatomy:
> T+2 delta coin-minus-market 15m = **0.679 / 0.735 / 0.885**

Static T0 looked stronger in D/V but collapsed on Reserve.
Temporal signal is lower in-sample but transports in the same direction.

### Lane 1
T0 multi-feature:
> **0.720 / 0.717 / 0.426**

T+3 side return:
> **0.779 / 0.725 / 0.843**

Temporal confirmation improves both D/V and, crucially, Reserve.

This is strong evidence that Lane 1 ambiguity is trajectory-dependent rather than solvable from static T0 alone.

---

# 6. Earliest useful horizon

Under the preregistered anatomy criterion of at least one canonical feature with same-direction D/V/R AUC >=0.60:

### Lane 0
> **T+1**

Feature:
`delta_f_coin_minus_market_15m`

AUC:
**0.668 / 0.669 / 0.814**

However, T+2 has a broader stable feature set (6 vs 1), so T+2 may be more robust for subsequent formal scanning.

### Lane 1
> **T+2**

Feature:
`confirm_side_return_pct`

AUC:
**0.706 / 0.627 / 0.852**

But T+3 is clearly the stronger research horizon:
- 9 stable features
- best all-split floor 0.725
- coherent side-return medians across all splits

---

# 7. Verdict

## SD-2B1

> **PASS_DIAGNOSTIC — TEMPORAL SIGNAL FOUND**

This does **not** mean a SHORT detector has passed.

What is established:

1. Temporal trajectory is materially more stable than the SD-2A static T0 models.
2. Lane 0 contains usable temporal anatomy as early as T+1, with broader support at T+2.
3. Lane 1 becomes clearly separable at T+3.
4. Lane 1 T+3 side return is especially compelling:
   - D **0.779**
   - V **0.725**
   - R **0.843**
5. Static T0 Reserve collapse is not repeated by the strongest temporal observables.
6. Lane 0 Reserve support remains small and requires caution.

What is **not** authorized:
- any threshold;
- delayed SHORT entry;
- probability score;
- multi-feature temporal model;
- paper / production deployment.

## Next stage

The next stage is **SD-2B2 — Single Temporal Feature Scan**.

It should:
- scan temporal features exhaustively but causally;
- freeze feature direction and threshold from Discovery/Validation only;
- keep Reserve sealed until candidate freeze;
- prioritize earliest useful horizons while accounting for winner attrition;
- determine whether the strong anatomy, especially Lane 1 T+3 side return, can become a stable operating rule.