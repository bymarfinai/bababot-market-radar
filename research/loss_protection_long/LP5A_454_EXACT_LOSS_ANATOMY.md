# LP-5A — Exact Loss Anatomy of Current 454 LONG OPEN Cohort

Status: **PASS — operational loss anatomy frozen.**

LP-5A deliberately abandons the full 1,236 discovery universe as the direct protector-design target and focuses on the **454 LONG trades actually opened by the current Stage 3C.7A detector**.

This stage is anatomy only. No protector threshold is created or deployed.

## Exact operational baseline

| Metric | Value |
|---|---:|
| OPEN trades | **454** |
| Realized positive | **176** |
| Realized non-positive | **278** |
| Historical WR | **38.77%** |
| Gross winner PnL | **+$604.56** |
| Gross loss PnL | **-$542.03** |
| Net historical PnL | **+$62.53** |

The LP-5 research target is therefore the **278 actual realized non-positive trades**, not META labels or the 1,236 discovery distribution.

## Loss anatomy by path

| Path | Loss N | Historical loss PnL | Share of gross loss $ | Median MFE | Median MAE |
|---|---:|---:|---:|---:|---:|
| **WRONG_DIRECTION** | **96** | **-$242.54** | **44.75%** | +0.239% | -1.218% |
| **STALL** | **24** | **-$118.82** | **21.92%** | +0.431% | -1.221% |
| **MISSED_OPPORTUNITY / RIGHT_THEN_FAILURE** | **158** | **-$180.68** | **33.33%** | +0.742% | -1.182% |
| **TOTAL** | **278** | **-$542.03** | **100%** | — | — |

This gives a clean two-part structure:

### Pre-0.50% failures
- **120 losses**
- **-$361.35**
- **66.67% of all gross loss dollars**

Composition:
- 96 WRONG_DIRECTION
- 24 STALL

### Reached >= +0.50% then failed
- **158 losses**
- **-$180.68**
- **33.33% of all gross loss dollars**

All are MISSED_OPPORTUNITY / RIGHT_THEN_FAILURE.

## Loss anatomy by maximum favorable excursion

| Historical max MFE | Loss N | Historical loss PnL | Share of gross loss $ |
|---|---:|---:|---:|
| <= 0% | 3 | -$9.95 | 1.84% |
| >0 to <0.18% | 20 | -$50.22 | 9.26% |
| **0.18% to <0.30%** | **49** | **-$115.66** | **21.34%** |
| **0.30% to <0.50%** | **48** | **-$185.52** | **34.23%** |
| 0.50% to <1.00% | 118 | -$124.62 | 22.99% |
| 1.00% to <2.00% | 34 | -$45.92 | 8.47% |
| 2.00% to <3.00% | 4 | -$5.72 | 1.05% |
| 3.00% to <5.00% | 1 | -$1.67 | 0.31% |
| >=5.00% | 1 | -$2.75 | 0.51% |

The key operational zone is:

> **MFE +0.18% to <+0.50%**

- 97 losses
- **-$301.18**
- **55.57% of all gross loss dollars**

This does **not** mean MFE can be used as a causal production feature. Final max MFE is hindsight anatomy only.

## Reconciliation with the known 121 sub-0.5 trades

Across all 454 OPEN trades:
- historical max MFE < +0.50%: **121**
- actual non-positive: **120**
- actual positive: **1**

The single positive sub-0.5 trade:
- TNSRUSDT
- MFE +0.3312%
- realized PnL about +$0.05
- path STALL

So the sub-0.5 outcome class is extremely loss-heavy in this cohort, but still cannot be known prospectively without a causal temporal discriminator.

## Target-class anatomy

| Class | Loss N | Loss PnL | Share of gross loss $ |
|---|---:|---:|---:|
| **NON_TARGET** | **265** | **-$530.07** | **97.79%** |
| STRONG_TARGET | 13 | -$11.95 | 2.21% |

All 13 strong-target failures are in the MISSED_OPPORTUNITY / RIGHT_THEN_FAILURE path.

Therefore the main Loss Protector problem is **not strong-target failure**. Almost all loss dollars come from non-target trades that still passed the current entry detector.

## MAE anatomy

| Historical MAE | Loss N | Loss PnL | Share loss $ |
|---|---:|---:|---:|
| > -0.35% | 7 | -$5.78 | 1.07% |
| -0.35% to -0.50% | 7 | -$4.02 | 0.74% |
| -0.50% to -1.00% | 75 | -$141.03 | 26.02% |
| -1.00% to -1.50% | 101 | -$158.80 | 29.30% |
| -1.50% to -2.00% | 46 | -$88.51 | 16.33% |
| <= -2.00% | 42 | -$143.89 | 26.55% |

Most loss dollars occur only after substantial adverse excursion, but MAE is outcome/path anatomy and is not sufficient by itself as a cut rule.

## Loss concentration

The gross -$542.03 is moderately concentrated:

| Worst losses | Cumulative loss | Share of gross loss |
|---|---:|---:|
| Worst 10 | -$90.33 | 16.67% |
| Worst 25 | -$159.89 | 29.50% |
| Worst 50 | -$245.65 | 45.32% |
| Worst 100 | -$372.00 | 68.63% |

So the problem is not only a handful of catastrophic outliers. A useful protector must improve a broad set of losing trades.

## Split / route sanity check

Losses remain present across all chronological splits:
- Discovery: 155 losses, -$286.52
- Validation: 65 losses, -$169.97
- Reserve: 58 losses, -$85.54

By route:
- FLOW_ALIGNED: 166 losses, -$283.88
- COUNTERFLOW: 112 losses, -$258.15

There is no single route or split that explains away the loss problem.

## LP-5A conclusions

1. The current 454 operational cohort is the correct direct target for Loss Protector research.
2. The exact loss pool is **278 trades / -$542.03**.
3. **Pre-0.5 failures dominate:** 120 trades and **-$361.35 = 66.67%** of gross loss dollars.
4. Within that, the **+0.18% to <+0.50% hindsight zone** contains only 97 losses but accounts for **-$301.18 = 55.57%** of all loss dollars.
5. WRONG_DIRECTION is the largest named path: **96 trades / -$242.54 / 44.75%**.
6. STALL is smaller in count but expensive: **24 trades / -$118.82 / 21.92%**.
7. RIGHT_THEN_FAILURE is large in count (158) but smaller in dollar leakage (**-$180.68 / 33.33%**).
8. Strong-target failures are not the main problem: only **-$11.95 / 2.21%** of gross loss dollars.
9. Non-target trades create **97.79%** of the gross loss pool.
10. Final MFE/MAE labels are hindsight descriptors. They must not be converted directly into protector rules.

## Next stage

**LP-5B — Operational Winner-vs-Loss Trajectory Anatomy**

Use the same frozen 454 cohort:
- 278 actual non-positive
- 176 actual positive

Compare the causal path features available while trades are still alive:
- T+1 / T+2 / T+3
- running MFE / running MAE
- side return
- recovery timing
- route/context features

Primary objective:

> identify which loss subtypes can be separated from the **176 actual winners of the same operational cohort**, rather than from winners in the broader 1,236 universe.

No protector is authorized by LP-5A.
