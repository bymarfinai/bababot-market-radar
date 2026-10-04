# LP-1B — Temporal Loss Anatomy for Full LONG 1,236

Status: **PASS — temporal anatomy frozen; no production protector rule frozen yet.**

LP-1B follows LP-1A and uses the same full resolved LONG universe of 1,236 trades. Future MFE/outcome fields are used only as labels. The causal explanatory inputs are the frozen T+1/T+2/T+3 snapshots already captured in the discovery dataset.

## Temporal snapshot timing

The frozen confirmation snapshots occur approximately at:

| Snapshot | Coverage | Median after entry | p90 |
|---|---:|---:|---:|
| T+1 | 1,234 / 1,236 | 0.62 min | 0.82 min |
| T+2 | 1,236 / 1,236 | 1.61 min | 1.82 min |
| T+3 | 1,236 / 1,236 | 2.61 min | 2.82 min |

## Critical timing guardrail: reaching +0.50%

There are 608 trades whose historical maximum MFE eventually reached >= +0.50%.

Time to first +0.50% MFE:
- p10: 0.11 min
- p25: 0.74 min
- median: **6.13 min**
- p75: **11.22 min**
- p90: **20.85 min**
- p95: **29.08 min**

Share that had already reached +0.50%:
- by 1 min: 25.82%
- by 2 min: 28.78%
- by 3 min: **32.24%**
- by 5 min: 41.61%
- by 10 min: 68.09%
- by 15 min: 82.73%
- by 20 min: 88.49%
- by 30 min: 95.07%

Recovered winners are especially slow:
- N = 228
- median time to +0.50%: **8.23 min**
- p75: **12.35 min**
- p90: **21.29 min**

Therefore a blanket 1–3 minute “has not reached +0.50%, therefore stall” rule is structurally unsafe.

## Duel A — TRUE WRONG DIRECTION vs RECOVERED WINNER

Population:
- TRUE WRONG DIRECTION: 555
- RECOVERED WINNER: 228
- total: 783

Three simple causal path variables:
- current side return
- running MFE
- running MAE

Three-feature logistic AUC, trained on chronological Development and evaluated D/V/R:

| Snapshot | D | V | R |
|---|---:|---:|---:|
| T+1 | 0.692 | 0.677 | 0.708 |
| T+2 | **0.788** | **0.817** | **0.799** |
| T+3 | **0.824** | **0.875** | **0.836** |

Strongest stable single feature is current side return:
- T+2 D/V/R AUC: 0.779 / 0.809 / 0.797
- T+3 D/V/R AUC: **0.811 / 0.872 / 0.823**
- lower side return is more associated with wrong direction.

Median at T+3:
- wrong direction side return: **-0.158%**
- recovered winner side return: **+0.178%**
- wrong direction running MFE: +0.145%
- recovered winner running MFE: +0.373%
- wrong direction running MAE: -0.307%
- recovered winner running MAE: -0.185%

Important: early adverse alone is not sufficient.
At T+3, running MAE <= -0.35% occurred in:
- wrong direction: 43.42%
- recovered winner: **18.86%**

At T+3, side return <= 0 occurred in:
- wrong direction: 75.86%
- recovered winner: **28.51%**

So a one-dimensional “red = cut” rule would still harm too many future winners.

### High-precision descriptive danger zone

A D-searched T+3 conjunction:
- side return <= -0.0785%
- running MFE <= +0.3033%
- running MAE <= -0.2381%

Descriptive D/V/R performance:
- bad recall: 49.69% / 53.15% / 43.44%
- bad precision: 91.95% / 96.72% / 89.83%
- recovered-winner harm: 9.66% / 5.13% / 13.64%

This is a candidate research zone for LP-2, **not a frozen production rule**.

## Duel B — eventual sub-0.50% failure vs future reach >= +0.50%

Population:
- actual non-positive with max MFE < +0.50%: 626
- future reaches >= +0.50%: 608
- total compared: 1,234
- the two rare realized-positive trades with max MFE < +0.50% are excluded from this binary duel.

Three-feature causal logistic AUC:

| Snapshot | D | V | R |
|---|---:|---:|---:|
| T+1 | 0.692 | 0.735 | 0.756 |
| T+2 | **0.776** | **0.811** | **0.847** |
| T+3 | **0.790** | **0.859** | **0.864** |

Strongest simple feature is running MFE:
- T+2 D/V/R AUC: 0.736 / 0.793 / 0.831
- T+3 D/V/R AUC: **0.770 / 0.833 / 0.856**
- lower running MFE is associated with eventual sub-0.5 failure.

Median at T+3:
- sub-0.5 failure running MFE: **+0.156%**
- future reach >=0.5 running MFE: **+0.409%**
- sub-0.5 failure side return: -0.144%
- future reach >=0.5 side return: +0.137%

However, a single T+3 MFE cutoff is too harmful.
D-optimal running-MFE threshold around +0.295% produced future-reacher harm of about:
- V: 27.68%
- R: 28.57%

Therefore BE must **not** be armed merely because T+3 MFE is still below ~0.30%.

### High-precision descriptive sub-0.5 danger zone

T+3 conjunction:
- side return <= -0.0690%
- running MFE <= +0.2444%
- running MAE <= -0.2633%

D/V/R:
- sub-0.5 failure recall: 40.45% / 40.74% / 33.33%
- precision: 80.00% / 88.71% / 86.54%
- future-reacher harm: **9.38% / 6.25% / 6.25%**

This is materially safer than a raw +0.18% BE trigger and is a candidate for LP-2 causal protector discovery.

## Duel C — RIGHT THEN FAILURE vs VALID RUNNER

Population:
- RIGHT_THEN_FAILURE / MISSED_OPPORTUNITY: 306
- valid runners = RECOVERED_WINNER + CLEAN_WINNER: 302
- total: 608

Simple path trio remains much weaker:

| Snapshot | D | V | R |
|---|---:|---:|---:|
| T+1 | 0.645 | 0.572 | 0.528 |
| T+2 | 0.641 | 0.627 | 0.611 |
| T+3 | 0.678 | 0.715 | 0.641 |

The best univariate structural features are not sufficiently stable on Reserve:
- T+3 distance-to-selected-extreme D/V/R: about 0.678 / 0.727 / **0.569**

Conclusion: a dedicated early RIGHT_THEN_FAILURE protector is not yet supported strongly enough and should be lower priority.

## LP-1B conclusions

1. **T+1 is too early** for reliable loss protection.
2. **T+2 already becomes useful**, especially for wrong-direction and sub-0.5 lanes.
3. **T+3 is the strongest early snapshot** for both priority problems:
   - wrong direction vs recovered winner: trio AUC 0.824 / 0.875 / 0.836
   - sub-0.5 failure vs future reach: trio AUC 0.790 / 0.859 / 0.864
4. Early MAE alone is unsafe because recovered winners frequently suffer adverse movement before recovery.
5. A fixed short timeout is unsafe: only 32.24% of future >=0.5 trades reach +0.5 by 3 minutes, and recovered winners have median time-to-0.5 of 8.23 minutes.
6. The BE concept should be reframed as a **multi-signal stall detector**, not “touch +0.18 then arm BE.”
7. High-precision 3-signal danger zones exist and are stable enough to justify LP-2 research.
8. RIGHT_THEN_FAILURE remains a secondary problem because early causal separation is materially weaker.

## Recommended next stage

**LP-2A — High-Precision Wrong-Direction Protector Discovery**
- start from the T+2/T+3 high-precision danger zones
- sweep causal thresholds and confirmation durations
- optimize loss dollars saved subject to winner-harm constraints

Then:

**LP-2B — Sub-0.5 Stall / BE Protector Discovery**
- replace raw BE arming with a causal stall gate
- optimize timing + side-return + running-MFE + running-MAE
- explicitly protect slow recovered winners

No protector is deployed or frozen by LP-1B.
