# LP-2A — High-Precision Wrong-Direction Protector Discovery

Status: **PASS — research candidate frozen, NOT production-ready.**

LP-2A continues the full-universe LONG Loss Protector track from LP-1A/LP-1B. The goal is to identify a causal early danger zone that catches a meaningful share of TRUE WRONG_DIRECTION trades while protecting RECOVERED_WINNER trades.

## Universe and split

- Full resolved LONG universe: **1,236**
- Chronological Development: **742**
- Validation: **247**
- Reserve: **247**

Target/control counts:

| Split | WRONG_DIRECTION | RECOVERED_WINNER | Realized positive |
|---|---:|---:|---:|
| Development | 323 | 145 | 201 |
| Validation | 110 | 39 | 52 |
| Reserve | 122 | 44 | 51 |

Thresholds were searched on Development. Candidate ranking used Development + Validation only. Reserve was opened only as the final gate.

## What was swept

LP-2A compared:
1. simple T+2 and T+3 two-/three-feature conjunctions using current side return, running MFE, and running MAE;
2. T+2→T+3 persistent confirmation rules;
3. richer T+3 causal conjunctions using the most stable LP-1B temporal features:
   - side return,
   - running MFE,
   - micro 3m return,
   - selected 5m slope,
   - close-z,
   - VWAP extension,
   - VWAP-extension delta,
   - structure-reversal score.

Development/Validation search guardrails for the high-precision lane:
- duel precision >= **92%**
- recovered-winner harm <= **6%**
- wrong-direction recall >= **12%**
- normalized net delta > 0

Reserve final gate:
- duel precision >= **90%**
- recovered-winner harm <= **10%**
- normalized net delta > 0

## LP-1B aggressive zone was rejected

The earlier descriptive T+3 danger zone:
- side return <= -0.0785%
- running MFE <= +0.3033%
- running MAE <= -0.2381%

was useful for anatomy but failed the stricter Reserve winner-preservation objective:

| Metric | D | V | R |
|---|---:|---:|---:|
| Wrong-direction recall | 49.85% | 52.73% | 43.44% |
| Duel precision | 92.00% | 96.67% | 89.83% |
| Recovered-winner harm | 9.66% | 5.13% | **13.64%** |
| Normalized net delta | +$137.15 | +$77.34 | +$50.73 |

The Reserve harm rate is too high for the high-precision protector lane.

## Selected LP-2A research candidate

Decision snapshot: **T+3**, median about **2.61 minutes after entry**.

All three conditions must hold:

1. `temporal__t3_confirm_side_return_pct <= 0.0000%`
2. `temporal__t3_confirm_mfe_pct <= +0.3026839575%`
3. `temporal__t3_f_f_selected_slope5_norm <= -0.0360707804`

Interpretation:

> by T+3 the LONG is not currently profitable, it has never built more than roughly +0.30% favorable excursion, and its normalized 5-minute selected-side slope has turned materially negative.

Notably, **MAE is not required** by the selected rule. This is desirable because LP-1A/LP-1B showed that many recovered winners experience meaningful early drawdown.

## D / V / R performance

| Metric | Development | Validation | Reserve |
|---|---:|---:|---:|
| Fired trades | 158 | 47 | 49 |
| WRONG_DIRECTION caught | 112 | 36 | 38 |
| Wrong-direction recall | **34.67%** | **32.73%** | **31.15%** |
| RECOVERED_WINNER hit | 8 | 1 | 4 |
| Recovered-winner harm rate | **5.52%** | **2.56%** | **9.09%** |
| Duel precision | **93.33%** | **97.30%** | **90.48%** |
| Normalized net delta | **+$102.73** | **+$44.93** | **+$51.49** |

Reserve passes the predeclared final gate.

## Full-universe descriptive application

Applied descriptively to all 1,236 rows:

- fires: **254**
- TRUE WRONG_DIRECTION caught: **186 / 555 = 33.51%**
- RECOVERED_WINNER hit: **13 / 228 = 5.70%**
- all realized-positive trades hit: **15 / 304 = 4.93%**
- wrong-vs-recovered precision: **93.47%**

Path-level normalized snapshot effect:

| Path | Fired N | Historical PnL | T+3 normalized close PnL | Delta |
|---|---:|---:|---:|---:|
| WRONG_DIRECTION | 186 | -$581.17 | -$367.04 | **+$214.13** |
| STALL | 15 | -$87.01 | -$25.65 | **+$61.36** |
| MISSED_OPPORTUNITY | 38 | -$46.88 | -$63.35 | **-$16.47** |
| RECOVERED_WINNER | 13 | +$36.47 | -$19.55 | **-$56.02** |
| CLEAN_WINNER | 2 | +$2.27 | -$1.56 | **-$3.84** |
| **TOTAL fired** | **254** | **-$676.31** | **-$477.16** | **+$199.16** |

If this normalized discovery delta were naively applied to the full historical universe, the full-universe result would move from about -$1,294.20 to about -$1,095.05.

**This is NOT an exact execution backtest.**

The T+3 close estimate uses the frozen T+3 side-return percentage multiplied by the frozen $5-per-1%-move normalization. It does not yet replay exact market execution, fees, slippage, or next-observable timing.

## Why the richer candidate won

A stricter simple T+3 side/MFE/MAE rule could also pass the final gate, but the richer rule using the selected 5m slope:
- kept Reserve recovered-winner harm at 9.09%;
- maintained Reserve precision above 90%;
- produced a stronger and more stable Reserve normalized net delta;
- avoided relying on MAE, which is known to overlap materially with recovered winners.

Two-snapshot T+2→T+3 persistence did **not** materially improve winner protection enough to justify the lower capture/net benefit. T+3 alone remains the preferred decision point for this research lane.

## LP-2A conclusion

**PASS.**

There is now a defensible high-precision wrong-direction candidate:

> T+3 side return <= 0  
> AND running MFE <= +0.3027%  
> AND selected 5m normalized slope <= -0.03607

It captures roughly one-third of TRUE WRONG_DIRECTION trades while keeping recovered-winner harm in single digits across the final Reserve gate.

However, it is still a **research candidate**, not a production protector.

Next recommended step:
- **LP-2B — Sub-0.5 Stall / BE Protector Discovery**, using the same causal discipline.
- After LP-2B, run a dedicated winner-harm and execution-realistic full-universe protector replay before any deployment.
