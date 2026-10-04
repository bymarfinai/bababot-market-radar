# Stage 3C.2 — Archetype-Specific Multi-Parameter Combination

## Scope

LONG only. Frozen strong-WIN target remains `META_WIN AND historical MFE >= 1.00%`.

- Flow-Aligned lane: 180 strong WIN vs 602 failures
- Counterflow lane: 65 strong WIN vs 233 failures
- No SHORT rows are included.

## Method

Each lane is modeled separately.

Raw combination search:
- 18 de-correlated numeric candidate parameters per lane
- every 2-, 3-, and 4-parameter subset tested
- class-weighted L2 logistic regression
- model fit on Discovery
- subset / regularization selected using Discovery + Validation only
- sealed Reserve is final-check only
- 20,145 logistic fits per lane

Rule-combination search:
- Stage 3C.1C loss-veto thresholds are reused
- 2-, 3-, and 4-rule voting structures tested
- Counterflow conservative veto constrains Discovery/Validation winner false-veto burden
- classification metrics and realized historical economics are reported separately

## 3C.2A — Flow-Aligned Continuation

Result: **FAIL for T0 multi-parameter separation**.

Best 2-parameter logistic combination:
- `f_median_abs_ret_5m_pct`
- `f_micro_rejection_wick_last`
- AUC Discovery / Validation / Reserve: **0.582 / 0.592 / 0.611**

Adding a third or fourth T0 parameter does not improve sealed Reserve. Rule-based combinations that look better on Discovery/Validation also deteriorate on Reserve.

Interpretation: the Flow-Aligned lane remains difficult to distinguish before entry. More T0 threshold search is not justified; temporal/trajectory confirmation is the next logical research layer.

## 3C.2B — Counterflow/Reversal

Counterflow remains materially more structured.

Best 3-parameter logistic combination:
- `f_f_coin_residual_5m_vs_btc`
- `f_new_momentum_curvature`
- `f_gate_price_drift_pct`
- AUC Discovery / Validation / Reserve: **0.676 / 0.688 / 0.718**

This is predictive, but not a stable strong detector because Validation remains below 0.70 and score-target correlation remains low.

### Conservative 4-rule Counterflow failure veto

Veto only when all four conditions are true:

1. `f_new_accel_5_vs_15 <= 0.6214308333`
2. `f_f_selected_slope5_norm <= 0.2612069909`
3. `f_f_coin_minus_market_30m >= -0.1486000362`
4. `f_f_coin_minus_market_15m <= 2.5904018610`

Results:

- Discovery: catches **91/141 failures (64.5%)**, false-vetoes **13/42 winners (31.0%)**, phi **0.285**
- Validation: catches **31/52 failures (59.6%)**, false-vetoes **4/16 winners (25.0%)**, phi **0.294**
- Reserve: catches **29/40 failures (72.5%)**, false-vetoes **1/7 winners (14.3%)**, phi **0.431**

Reserve retained pool:
- **17 trades**
- **6 strong WIN + 11 failure**
- strong-WIN share: **35.3%**, versus baseline **7/47 = 14.9%**
- realized historical PnL: **-$5.92**
- average realized return: **-0.070% / trade**

So classification improves materially, but economics remain slightly negative.

## Integrity check

A different rule combination can look profitable on Discovery and Validation and still fail on Reserve. Therefore no candidate is promoted based on in-sample economics.

## Verdict

**Stage 3C.2 = PARTIAL PASS, research-only.**

- 3C.2A Flow-Aligned: **FAIL**
- 3C.2B Counterflow: **PROMISING VETO, NOT FINAL**
- No production entry/veto authority changes.
- Do not build a final unified T0 LONG detector yet.
- Recommended next research: preserve the Counterflow veto candidate and use temporal/trajectory confirmation to solve the Flow-Aligned lane before unified LONG validation.
