# SHORT-CT5B — DROP vs RESCUE Architecture Test

Status: **PASS architecture repair / primary = block ALT backdoor + T+2->T+3 confirmation-acceleration gate / profitability still FAIL**

## Objective

CT-5A established that the +0.075% SHORT confirmation floor is useful mainly as a veto, but that part of its benefit is given back when marginal trades are rescued into T+3.

CT-5B tests whether the architecture should:

1. keep T+1 -> T+2 unchanged;
2. block the T3 source-switch path where a stricter Lane-1 confirmation fails but ALT-T3 re-admits the same trade;
3. require materially stronger evidence before rescuing T+2 -> T+3;
4. compare that conditional rescue against blanket T+2 -> T+3 DROP as a stress control.

No production or runtime rule is changed.

## Frozen baseline

Everything except the tested rescue decision is frozen:

- SHORT temporal confirmation floor: **+0.075%**
- S10D fast T0
- S10C Lane-0 recovery
- ALT-T3 definition
- CT-4 exact execution contract
- V4.3 SHORT-LS4
- BE0.10 only on V4.3 NO_ACTION
- fee / slippage / notional metadata
- T+1 -> T+2 unchanged

CT-4 +0.075% baseline:

| Scope | Selected | Executable | Exec strong | Protected WR | Protected PnL |
|---|---:|---:|---:|---:|---:|
| Research | 333 | 291 | 78 | 33.68% | **-$135.33** |
| Fresh | 754 | 640 | 168 | 33.28% | **-$245.06** |
| Combined | 1,087 | 931 | 246 | 33.40% | **-$380.39** |

## Candidate A — block T3 threshold-fail -> ALT backdoor

CT-5A found four T3 source-switch trades:

- 4 selected
- 3 executable
- **0 strong**
- all 3 executable trades are severe HIST_TIME_FALLBACK
- protected PnL: **-$8.48**

Composition:

- Research Validation: LIGHT, -$2.04
- Research Reserve: 币安人生, -$3.35
- Fresh Oct 3: CYS, -$3.09
- Fresh Oct 1: 1000000BOB, no executable entry

Blocking only this path gives:

- Research: **-$135.33 -> -$129.94**, +$5.39
- Fresh: **-$245.06 -> -$241.96**, +$3.09
- Combined improvement: **+$8.48**
- strong lost: **0**

This closes the architectural loophole without disabling ALT-T3 generally.

## Candidate B — T+2 -> T+3 confirmation acceleration

Raw T3 confirmation alone has heavy winner / non-target overlap.

Therefore CT-5B does not fit a new absolute T3 confirmation cutoff.

Instead, rescue quality is expressed as a monotonic causal quantity available at T3:

> **confirmation acceleration = T3 confirm side return - T2 confirm side return**

The rationale is architectural:

> a trade that already failed +0.075% at T2 should only receive an additional T3 rescue if T3 contributes a meaningful new confirmation impulse, rather than barely crossing the same threshold one minute later.

Coarse development grid:

| Minimum T3-T2 confirmation acceleration | Combined PnL improvement | Strong dropped | Interpretation |
|---:|---:|---:|---|
| +0.050 pp | +$6.37 | 0 | safe but weak |
| **+0.075 pp** | **+$15.73** | **0** | **winner-preserving Pareto point** |
| +0.100 pp | +$14.52 | 1 | starts deleting a research strong winner |
| +0.125 pp | +$21.42 | 1 | more pruning, winner loss |
| +0.150 pp | +$26.23 | 1 | more pruning, winner loss |

The +0.075 pp candidate is carried because:

1. it has a direct relationship to the frozen +0.075% confirmation floor;
2. it is the strongest tested zero-strong-loss gate;
3. moving to +0.100 pp immediately removes EDEN, a profitable research strong winner;
4. it is monotonic and causal;
5. it does not introduce a narrow raw-feature band.

### T+2 -> T+3 before gate

- 21 selected
- 17 executable
- 5 strong selected / 5 executable
- protected PnL: **-$31.32**
- strong PnL: **+$11.35**
- non-target PnL: **-$42.67**
- severe fallback: **9 / -$43.44**

### T+2 -> T+3 after +0.075 pp acceleration gate

- 16 selected
- 13 executable
- **5 strong selected / 5 executable**
- protected PnL: **-$15.59**
- strong PnL: **unchanged +$11.35**
- non-target PnL: **-$26.94**
- severe fallback: **5 / -$27.71**

Removed by the gate:

- Research Discovery 币安人生: -$3.11 severe
- Research Discovery ZEST: no executable entry
- Fresh Oct 2 IOST: -$5.18 severe
- Fresh Oct 3 MELANIA: -$3.26 severe
- Fresh Oct 3 ZAMA: -$4.19 severe

Thus the gate removes:

> **4 executable severe non-targets / $15.73 loss**

while removing:

> **0 strong winners**

## Primary CT-5B architecture

Primary:

> **1. Block only T3 LANE1_TEMPORAL -> ALT_T3 source-switch after stricter-threshold failure**
>
> **2. For T+2 -> T+3, RESCUE only when T3 confirmation - T2 confirmation >= +0.075 percentage points**
>
> **3. Leave T+1 -> T+2 unchanged**
>
> **4. Leave independently valid ALT-T3 entries unchanged**

### Headline result

| Scope | CT-4 +0.075 baseline | CT-5B primary | Improvement |
|---|---:|---:|---:|
| Research | -$135.33 | **-$126.83** | **+$8.50** |
| Fresh | -$245.06 | **-$229.34** | **+$15.71** |
| Combined | -$380.39 | **-$356.18** | **+$24.21** |

Strong retention:

- Research executable strong: **78 -> 78 = 100%**
- Fresh executable strong: **168 -> 168 = 100%**
- Combined executable strong: **246 -> 246 = 100%**

Dropped primary cohort:

- 9 selected
- 7 executable
- **0 strong**
- **7 / 7 executable = severe non-target HIST_TIME_FALLBACK**
- dropped PnL: **-$24.21**

This is a very clean architecture-level pruning result.

## Chronological stability

Primary CT-5B delta versus CT-4 +0.075:

| Block | PnL improvement | Strong dropped |
|---|---:|---:|
| Research Discovery | **+$3.11** | 0 |
| Research Validation | **+$2.04** | 0 |
| Research Reserve | **+$3.35** | 0 |
| Fresh Oct 1 | **$0.00** | 0 |
| Fresh Oct 2 | **+$5.18** | 0 |
| Fresh Oct 3 | **+$10.54** | 0 |

Result:

> **5 / 6 blocks improve, 1 / 6 is neutral, 0 / 6 worsen.**

No chronological block loses a strong winner.

## T+3 lane effect

CT-4 +0.075 T3:

- 173 selected
- 131 executable
- 38 selected strong / 34 executable strong
- protected PnL: **-$57.09**
- strong PnL: **+$91.47**
- non-target PnL: **-$148.56**
- severe fallback: **35**

After primary CT-5B:

- 164 selected
- 124 executable
- **38 selected strong / 34 executable strong unchanged**
- protected PnL: **-$32.88**
- strong PnL: **+$91.47 unchanged**
- non-target PnL: **-$124.35**
- severe fallback: **28**

T3 improvement:

> **+$24.21**

Severe fallback reduction:

> **35 -> 28**

Protected T3 WR:

> **34.35% -> 36.29%**

This directly addresses the architecture weakness identified in CT-5A.

## Blanket T+2 -> T+3 DROP stress control

Blanket DROP is economically stronger in aggregate:

- Research: **-$121.36**
- Fresh: **-$227.70**
- combined improvement: **+$31.32**

Adding the ALT source-switch block gives the diagnostic upper bound:

- Research: **-$115.97**
- Fresh: **-$224.61**
- combined improvement: **+$39.80**

But blanket DROP fails the winner-preservation / block-stability test:

- removes **5 strong winners**
- research executable strong retention falls to **98.72%**
- fresh executable strong retention falls to **97.62%**
- Fresh Oct 2 gets **worse by $2.997**
- Fresh Oct 2 loses **4 strong winners**
- the dropped T+2->T+3 strong cohort contains **+$11.35** protected value

Therefore:

> **blanket T+2 -> T+3 DROP is rejected as the primary architecture.**

It remains only a stress/control upper bound.

## CT-5B verdict

> **CT-5B = PASS as an architecture repair.**

Primary research candidate:

> **BLOCK threshold-fail T3 source-switch -> ALT**
>
> **AND**
>
> **T+2 -> T+3 rescue requires >= +0.075 pp confirmation acceleration**

Why this is preferred:

- +$24.21 combined protected-PnL improvement
- +$8.50 research
- +$15.71 fresh
- 100% executable-strong retention
- 7 severe executable non-targets removed
- 0 executable winners removed
- 5/6 blocks improve
- 1/6 neutral
- 0/6 worsen
- T+3 loss reduced from -$57.09 to -$32.88
- T+1 -> T+2 remains untouched
- independently valid ALT-T3 remains available

However profitability still fails:

> Research remains **-$126.83**
>
> Fresh remains **-$229.34**

Therefore:

- no production promotion;
- no paper-entry activation;
- no runtime detector change;
- PAUSE_ENTRIES safety boundary remains untouched;
- lifecycle exits remain untouched.

## Validation warning

All Research + Fresh blocks used here are already development-visible.

The +0.075 pp acceleration gate is therefore a **development-frozen architecture candidate**, not a newly sealed validation result.

A later unseen cohort is still required before runtime authority.

## Next recommended stage

> **CT-5C — interaction / residual architecture test**

Minimum objective:

1. freeze the CT-5B primary rescue architecture;
2. rebuild any regime-normalized suppressor statistics on the new +0.075% / CT-5B selected population rather than mechanically reusing old S10J percentiles;
3. test whether the accepted S10J concepts still add value without overlapping the newly removed T3 failures;
4. preserve the CT-5B 100% strong-retention result as a comparison gate;
5. remain research-only until a new unseen cohort exists.