# LP-5C — Raw 5-Second Temporal Anatomy, Current 454 LONG

Status: **PASS — raw 5s temporal anatomy frozen. No protector rule is authorized yet.**

## Contract

Universe:
- current Stage 3C.7A LONG OPEN cohort: **454 trades**
- actual winners: **176**
- actual non-positive: **278**

Market path source:
- Binance USD-M daily `aggTrades` historical archive
- **300 / 300 symbol-day files available**
- no archive errors

Sampling:
- exact boundaries every 5 seconds from **60s through 120s after actual entry**
- latest aggregate-trade price at or before each boundary, with carry-forward
- running MFE/MAE built from archived trades since entry
- a trade is included only when its historical close is **strictly after** the boundary

Split:
- frozen chronological Development / Validation / Reserve boundaries inherited from the 1,236 LONG research universe

Benchmark model:
- current side return
- running MFE
- running MAE
- logistic score trained on Development separately at each timestamp
- thresholds/model weights are never fitted on Validation or Reserve

## Predeclared stability gates

Wrong Direction:
- minimum D/V/R AUC >= **0.75**
- at least **60% of original 96 WD trades** still alive

Pre-0.5 loss:
- minimum D/V/R AUC >= **0.70**
- at least **70% of original 120 pre-0.5 losses** still alive

These gates were declared before reading the raw-5s result curve.

## Main result

- earliest stable Pre-0.5 timestamp: **65 seconds**
- earliest stable Wrong Direction timestamp: **75 seconds**
- earliest timestamp where **both lanes simultaneously pass**: **75 seconds**

Therefore the practical early protector research window shifts from T+2/T+3 to approximately:

> **75–90 seconds after entry**

This is an anatomy finding, not a production stop time.

## Wrong Direction vs Winner curve

| Time | D AUC | V AUC | R AUC | WD alive | Winners alive |
|---|---:|---:|---:|---:|---:|
| 60s | 0.780 | 0.766 | **0.697** | 83 | 168 |
| 65s | 0.792 | 0.820 | **0.689** | 82 | 166 |
| 70s | 0.784 | 0.795 | **0.733** | 79 | 166 |
| **75s** | **0.822** | **0.796** | **0.777** | **78** | **165** |
| 80s | 0.816 | 0.809 | 0.819 | 78 | 165 |
| 85s | 0.827 | 0.817 | 0.792 | 77 | 165 |
| 90s | 0.831 | 0.807 | 0.832 | 76 | 165 |
| 95s | 0.826 | 0.826 | 0.857 | 76 | 164 |
| 100s | 0.849 | 0.820 | 0.886 | 74 | 164 |
| 105s | 0.844 | 0.819 | 0.919 | 72 | 164 |
| 110s | 0.851 | 0.791 | 0.900 | 72 | 163 |
| 115s | 0.837 | 0.765 | 0.912 | 68 | 161 |
| 120s | 0.845 | 0.818 | 0.913 | 65 | 161 |

At 75 seconds:
- WD coverage = **78 / 96 = 81.25%**
- winner availability = **165 / 176 = 93.75%**
- all three D/V/R AUCs exceed 0.75

The Reserve weakness visible at 60–70 seconds disappears at 75 seconds.

## Pre-0.5 loss vs Winner curve

| Time | D AUC | V AUC | R AUC | Pre-0.5 alive | Winners alive |
|---|---:|---:|---:|---:|---:|
| 60s | 0.749 | 0.762 | **0.696** | 107 | 168 |
| **65s** | **0.762** | **0.789** | **0.704** | **106** | **166** |
| 70s | 0.753 | 0.746 | 0.746 | 103 | 166 |
| **75s** | **0.775** | **0.760** | **0.770** | **102** | **165** |
| 80s | 0.774 | 0.758 | 0.812 | 102 | 165 |
| 85s | 0.786 | 0.786 | 0.792 | 101 | 165 |
| 90s | 0.785 | 0.769 | 0.821 | 100 | 165 |
| 95s | 0.769 | 0.781 | 0.843 | 100 | 164 |
| 100s | 0.799 | 0.781 | 0.868 | 98 | 164 |
| 105s | 0.794 | 0.765 | 0.891 | 96 | 164 |
| 110s | 0.796 | 0.753 | 0.879 | 96 | 163 |
| 115s | 0.785 | 0.734 | 0.895 | 92 | 161 |
| 120s | 0.792 | 0.780 | 0.900 | 89 | 161 |

At 75 seconds:
- pre-0.5 loss coverage = **102 / 120 = 85.0%**
- winner availability = **165 / 176 = 93.75%**
- D/V/R AUC = **0.775 / 0.760 / 0.770**

So 75s is the earliest common stable point for both priority loss lanes.

## Anatomy at the 75-second joint point

### Wrong Direction
Median current side return:
- WD: **-0.041%**
- winner: **+0.157%**

Median running MFE:
- WD: **+0.160%**
- winner: **+0.303%**

Median running MAE:
- WD: **-0.149%**
- winner: **-0.107%**

### Pre-0.5 losses
Median current side return:
- pre-0.5 loss: **+0.019%**
- winner: **+0.157%**

Median running MFE:
- pre-0.5 loss: **+0.176%**
- winner: **+0.303%**

Median running MAE:
- pre-0.5 loss: **-0.134%**
- winner: **-0.107%**

The signal is again not merely “large drawdown.”

The stronger structural distinction is:

> **bad trades have failed to build favorable progress quickly enough by ~75 seconds.**

## Single-feature behavior

For Wrong Direction, current side return is especially informative:
- at 75s D/V/R low-is-bad AUC ≈ **0.805 / 0.800 / 0.750**
- at 80s ≈ **0.806 / 0.805 / 0.805**
- at 90s ≈ **0.821 / 0.787 / 0.834**

Running MFE is also stable:
- at 75s ≈ **0.751 / 0.739 / 0.773**
- at 80s ≈ **0.762 / 0.780 / 0.775**
- at 90s ≈ **0.760 / 0.780 / 0.786**

MAE is weaker and less stable than side-return/MFE, reinforcing the prior conclusion that an ordinary drawdown stop is not the right design.

## LP-5C conclusion

**PASS.**

1. The raw archive confirms the LP-5B hypothesis.
2. **60 seconds is too early** because Reserve discrimination is not yet stable.
3. **75 seconds is the earliest common stable point** for both Wrong Direction and Pre-0.5 loss.
4. At 75s, **81.25% of WD** and **85.0% of pre-0.5 losses** are still alive, while 93.75% of winners remain available as controls.
5. Waiting to 100–120s improves Reserve AUC further, but sacrifices additional loss coverage.
6. The most promising protector-development zone is **75–90 seconds**, not T+3.
7. Side return + running MFE carry most of the separation; MAE is secondary.
8. No threshold, exit, or deployed Loss Protector is frozen by LP-5C.

## Recommended next stage

**LP-5D — High-Precision 75–90s Protector Discovery**

Rules:
- search timestamps only at 75/80/85/90s
- threshold search on Development only
- Validation screening
- Reserve final gate once
- explicitly constrain actual-winner harm
- immediately follow any surviving candidate with archive execution replay; do not rely on normalized dollar estimates

The objective is not maximum recall.

The objective is:

> save a high-confidence subset of the 120 pre-0.5 / 96 wrong-direction losses while keeping actual-winner harm very low.
