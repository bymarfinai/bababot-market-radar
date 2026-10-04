# Stage 3C.1B — Winner Anatomy & Clustering

## Frozen contract

- LONG universe: **1,236**
- META_WIN: **401**
- META_LOSS: **835**
- Strong WIN target: **245 = META_WIN AND historical MFE >= 1.00%**
- Weak WIN: **156 = META_WIN AND historical MFE < 1.00%**
- Split remains chronological:
  - Discovery: 741 total = 162 strong WIN / 94 weak WIN / 485 LOSS
  - Validation: 247 total = 45 strong WIN / 31 weak WIN / 171 LOSS
  - Sealed reserve: 248 total = 38 strong WIN / 31 weak WIN / 179 LOSS

## Three contrast tests

1. All META_WIN vs META_LOSS:
   - best stable single-feature AUC floor ≈ **0.557** (`f_f_coin_minus_market_5m`)
2. Strong WIN vs weak WIN:
   - best stable single-feature AUC floor ≈ **0.531**
   - strong and weak winners are almost indistinguishable at T0
3. Strong WIN vs pure META_LOSS:
   - best stable single-feature AUC floor ≈ **0.549** (`f_micro_selected_vwap_extension_20`)

Weak-WIN contamination is therefore **not** the sole cause of weak Stage 3C.1 separation.

## Winner clustering

Fit only on Discovery strong winners.

- 224 T0 features
- 193 sufficiently populated numeric features
- 142 numeric after >0.95 correlation pruning
- 27 one-hot categorical columns
- 169 model columns
- StandardScaler + PCA
- 24 PCA components explain about **80.8%** of Discovery winner variance
- KMeans k=2..8
- best structure: **k=2**
- Discovery silhouette ≈ **0.171**
- bootstrap ARI median ≈ **0.812**

### Archetype A — COUNTERFLOW_REVERSAL

- **65 / 245 = 26.5%**
- D/V/R = 42 / 16 / 7
- flow family: OPPOSITE 35, NEUTRAL 25, ALIGNED 5
- median MFE **1.521%**
- realized PnL **+$195.27**
- avg realized return/trade **+0.601%**
- positive realized rate **87.7%**

Typical anatomy: lower taker share, weak/negative 1m side return, negative 1m-vs-3m micro acceleration, positive price-vs-flow gap/fade pressure.

Subtype-specific one-feature AUC examples vs pure LOSS:
- `f_new_micro_accel_1_vs_3`: D/V/R ≈ **0.777 / 0.742 / 0.970**
- `f_gate_taker_share_for_selected`: **0.834 / 0.783 / 0.737**
- `f_new_gate_price_x_flow_gap`: **0.840 / 0.806 / 0.732**

Reserve support is only 7 targets, so this is promising **low-support** anatomy, not final detector evidence.

### Archetype B — FLOW_ALIGNED_CONTINUATION

- **180 / 245 = 73.5%**
- D/V/R = 120 / 29 / 31
- flow family: ALIGNED 164, NEUTRAL 14, OPPOSITE 2
- median MFE **1.577%**
- realized PnL **+$633.68**
- avg realized return/trade **+0.704%**
- positive realized rate **92.8%**

Typical anatomy: higher aligned taker share, positive 1m side return, positive flow support, smaller price-vs-flow gap.

Subtype-specific AUC examples vs pure LOSS:
- `f_gate_side_ret_1m_pct`: **0.586 / 0.659 / 0.613**
- `f_new_flow_support`: **0.621 / 0.614 / 0.585**
- `f_micro_selected_vwap_extension_20`: **0.586 / 0.585 / 0.576**

## Signal cancellation

This is the central result.

- `f_gate_taker_share_for_selected`
  - all strong WIN vs LOSS raw AUC ≈ **0.490**
  - COUNTERFLOW_REVERSAL raw AUC ≈ **0.187** (LOW direction)
  - FLOW_ALIGNED_CONTINUATION raw AUC ≈ **0.599** (HIGH direction)
- `f_gate_side_ret_1m_pct`
  - aggregate ≈ **0.517**
  - counterflow ≈ **0.272** (LOW)
  - continuation ≈ **0.605** (HIGH)
- `f_new_flow_support`
  - aggregate ≈ **0.502**
  - counterflow ≈ **0.196** (LOW)
  - continuation ≈ **0.612** (HIGH)

Therefore a near-zero aggregate association does **not** mean the parameter is irrelevant. A universal direction is wrong for a heterogeneous winner population.

## Verdict

**WINNER HETEROGENEITY CONFIRMED.**

No subtype has entry authority yet. Stage 3C.2 should tune separate multi-parameter combinations for the two frozen archetypes instead of forcing one universal LONG winner rule.
