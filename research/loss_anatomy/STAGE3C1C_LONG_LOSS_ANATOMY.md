# Stage 3C.1C — LONG LOSS Anatomy & Failure Clustering

## Frozen scope

- LONG META_LOSS universe: **835**
- Discovery / Validation / Sealed Reserve LOSS: **485 / 171 / 179**
- Reference strong-WIN archetypes remain frozen from Stage 3C.1B:
  - **180 FLOW_ALIGNED_CONTINUATION**
  - **65 COUNTERFLOW_REVERSAL**
- SHORT is excluded.

## Loss clustering

Clustering is fit on Discovery META_LOSS only, using the same T0 feature family and chronological split discipline.

Best broad structure: **k = 2**
- Discovery silhouette: **0.161**
- bootstrap median ARI: **0.843**
- PCA retained about **80.3%** of Discovery variance

### FLOW_ALIGNED_FAILURE

- **602 / 835 = 72.1%**
- Discovery / Validation / Reserve: **344 / 119 / 139**
- historical realized PnL: about **-$1,462.56**
- average realized return/trade: about **-0.486%**
- median MFE: about **0.246%**
- median MAE: about **-0.950%**
- TRUE_WRONG_DIRECTION: **394 / 602 = 65.4%**
- RIGHT_THEN_FAILURE: **122 / 602 = 20.3%**

### COUNTERFLOW_FAILURE

- **233 / 835 = 27.9%**
- Discovery / Validation / Reserve: **141 / 52 / 40**
- historical realized PnL: about **-$549.32**
- average realized return/trade: about **-0.472%**
- median MFE: about **0.340%**
- median MAE: about **-0.921%**
- TRUE_WRONG_DIRECTION: **121 / 233 = 51.9%**
- RIGHT_THEN_FAILURE: **79 / 233 = 33.9%**

## Key structural finding

LOSS composition is nearly the same as strong-WIN composition:

- LOSS: **72.1% aligned / 27.9% counterflow**
- strong WIN: **73.5% continuation / 26.5% counterflow**

Therefore archetype identity alone is not a detector. Research must distinguish WIN from LOSS **within the same archetype**.

## Within-archetype separation

### Flow-Aligned Continuation WIN vs Flow-Aligned Failure

T0 separation remains weak. Best stable single-feature AUC floor is about **0.551**.

Representative features:
- selected VWAP extension: D/V/R AUC about **0.571 / 0.571 / 0.551**
- median absolute 5m movement: **0.583 / 0.549 / 0.597**
- funding rate, lower for WIN: **0.546 / 0.590 / 0.555**
- micro side return 10m: **0.548 / 0.586 / 0.545**

This lane still needs multi-parameter and/or temporal separation.

### Counterflow/Reversal WIN vs Counterflow Failure

This lane is materially more separable at T0:

- acceleration 5m vs 15m: **0.648 / 0.655 / 0.696**
- coin residual 5m vs BTC: **0.644 / 0.636 / 0.832**
- selected slope5 norm: **0.628 / 0.673 / 0.850**
- momentum curvature: **0.609 / 0.643 / 0.632**
- raw 5m return: **0.629 / 0.601 / 0.779**

A discovery+validation tuned example failure-veto rule:

`f_new_accel_5_vs_15 <= 0.621431`

- Discovery: catches **102 / 141** counterflow failures; false-vetoes **17 / 42** counterflow WINs
- Validation: catches **40 / 52** failures; false-vetoes **7 / 16** WINs
- Reserve: catches **30 / 40** failures; false-vetoes **3 / 7** WINs

This is promising anatomy, not production-ready. Reserve contains only **7** counterflow strong WINs.

## Verdict

**LOSS HETEROGENEITY CONFIRMED.**

- Flow-Aligned Failure is the dominant loss lane, but T0 separation from Flow-Aligned Continuation WIN remains weak.
- Counterflow Failure is smaller but substantially more distinguishable from Counterflow WIN using momentum and market-relative features.
- No Stage 3C.1C cluster or threshold has entry/veto authority.
- Stage 3C.2 must use separate archetype-specific combination research:
  1. Flow-Aligned Continuation WIN vs Flow-Aligned Failure
  2. Counterflow/Reversal WIN vs Counterflow Failure
