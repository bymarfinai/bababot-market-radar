# SD-1A — Full SHORT Universe Anatomy

Status: **PASS / FROZEN**

## Trading funnel

> **655 resolved SHORT candidates → 163 META_WIN / 492 META_LOSS → 99 strong WIN / 556 non-target**

Strong WIN remains independently defined for SHORT as:

`META_WIN AND historical_max_mfe_pct >= 1.00%`

No LONG threshold, feature sign, router rule, or temporal threshold is imported.

## Source integrity

- all SHORT rows before timeout exclusion: **791**
- SHORT TIMEOUT excluded from resolved universe: **136**
- resolved SHORT frozen universe: **655**
- T0 source rows: **2,175**
- triple-barrier rows: **2,175**
- temporal rows: **2,175**
- T0 feature columns: **231**
- T0 feature coverage on frozen SHORT: **231 / 231 fully populated**
- MFE coverage: **655 / 655**

The frozen reference therefore exactly verifies the playbook counts:
- **163 META_WIN**
- **492 META_LOSS**
- **99 strong WIN**

## Historical economics

| Cohort | N | Realized positive | Historical PnL | Median MFE | Peak-MFE $ equivalent |
|---|---:|---:|---:|---:|---:|
| Full SHORT | 655 | 118 (18.02%) | **-$974.69** | 0.540% | **$2,434.93** |
| Strong WIN | 99 | 91 | **+$266.42** | 1.483% | **$973.16** |
| Weak META_WIN | 64 | 12 | **-$33.98** | 0.762% | $223.46 |
| META_LOSS | 492 | 15 | **-$1,207.12** | 0.341% | **$1,238.30** |

Important: the historical realized result is very poor despite substantial favorable excursion. Track A therefore must remain separated from exit quality.

## Chronological split freeze

| Split | N | META_WIN | META_LOSS | Strong WIN | Strong-WIN prevalence | Historical PnL |
|---|---:|---:|---:|---:|---:|---:|
| Discovery | 393 | 98 | 295 | 59 | 15.01% | -$606.14 |
| Validation | 131 | 41 | 90 | 27 | 20.61% | -$139.34 |
| Reserve | 131 | 24 | 107 | 13 | 9.92% | -$229.20 |

The target prevalence is not stationary: Validation is richer in strong winners and Reserve is materially poorer. Future SD stages must therefore report D/V/R separately and must not judge a rule only on aggregate performance.

## MFE distribution

| Historical MFE | N | META_WIN | META_LOSS | Strong WIN | Historical PnL | Peak-MFE $ equivalent |
|---|---:|---:|---:|---:|---:|---:|
| <0.30% | 208 | 5 | 203 | 0 | -$614.10 | $164.82 |
| 0.30–<0.50% | 95 | 1 | 94 | 0 | -$347.09 | $176.45 |
| 0.50–<1.00% | 203 | 58 | 145 | 0 | -$229.18 | $717.16 |
| 1.00–<1.50% | 79 | 51 | 28 | 51 | +$28.52 | $468.36 |
| 1.50–<2.00% | 35 | 21 | 14 | 21 | +$26.85 | $298.59 |
| 2.00–<3.00% | 24 | 20 | 4 | 20 | +$82.15 | $289.65 |
| 3.00–<5.00% | 5 | 2 | 3 | 2 | +$13.46 | $89.50 |
| >=5.00% | 6 | 5 | 1 | 5 | +$64.71 | $230.41 |

Two immediate anatomy facts:

1. **303 / 655** SHORT trades never exceed +0.50% MFE.
2. **149** trades reach at least +1% MFE, but only **99** are strong META_WIN; **50 META_LOSS** also reached >=1% MFE before losing the barrier race.

Therefore MFE magnitude alone cannot be used as the SHORT entry target.

## Temporal data readiness

Raw T+1/T+2/T+3 feature coverage is complete: **655 / 655** at each horizon.

After strict causal censoring for trades whose META outcome had already resolved:

| Horizon | Causal survivors | Coverage |
|---|---:|---:|
| T+1 | 610 / 655 | **93.13%** |
| T+2 | 552 / 655 | **84.27%** |
| T+3 | 479 / 655 | **73.13%** |

This is sufficient to support later SHORT temporal-confirmation research without reconstructing the market path first.

## Historical WD1 outcome anatomy

| WD1 outcome | N | Strong WIN | Strong-WIN prevalence | Historical PnL |
|---|---:|---:|---:|---:|
| CORRECT_RUNNER | 24 | 15 | 62.50% | +$53.04 |
| RECOVERED_DRAWDOWN | 93 | **76** | **81.72%** | +$237.77 |
| RIGHT_THEN_FAILURE | 235 | 8 | 3.40% | -$304.31 |
| STALL_NO_EDGE | 45 | 0 | 0% | -$193.15 |
| TRUE_WRONG_DIRECTION | 258 | 0 | 0% | -$768.04 |

The 99 strong winners consist of:
- **76 RECOVERED_DRAWDOWN (76.77%)**
- **15 CORRECT_RUNNER (15.15%)**
- **8 RIGHT_THEN_FAILURE (8.08%)**

This is a major SHORT-specific clue, but it is anatomy only. SD-1A does not authorize a recovery-based detector rule.

## Main SD-1A conclusions

1. The independent SHORT universe is now reproducibly frozen at **655** resolved trades.
2. The strong target is exactly **99 / 655 = 15.11%**.
3. SHORT has substantial positive-excursion opportunity despite historical aggregate PnL of **-$974.69**.
4. Reserve strong-WIN prevalence is only **9.92%**, materially below Discovery and Validation; stability checks are mandatory.
5. Most strong SHORT winners are historically classified as **RECOVERED_DRAWDOWN**, suggesting SHORT winner anatomy may differ materially from a simple clean-continuation model.
6. T+1/T+2/T+3 temporal coverage is sufficient for later causal confirmation work.
7. No SHORT detector threshold has been tuned yet.

## Decision

**SD-1A = PASS_FREEZE.**

Next stage under the frozen playbook is **SD-1B / SHORT-S2 — exhaustive single-feature T0 scan** against:
- 655 candidates
- 99 strong WIN
- 556 non-target
- chronological D/V/R = 393 / 131 / 131

Reserve remains sealed for tuning.