# SHORT-CT6C — T2 High-Precision Low-MFE Veto

Status: **PASS high-precision T2 veto / clean but limited coverage**

## Objective

CT-6C converts the CT-6B T2 feature-separation findings into a simple causal veto candidate.

The target is not maximum rejection.

The target is:

> remove a clean subset of low-MFE T2 trades while preserving executable TARGET-MFE and strong winners.

No runtime or paper-entry rule is changed.

## Frozen research contract

Lane:

> **T2 only**

Research labels:

- BAD-A: future max MFE <0.30%
- BAD-B: 0.30% <= future max MFE <0.50%
- GRAY: 0.50% <= future max MFE <1.00%
- TARGET-MFE: future max MFE >=1.00%

MFE remains a research label only.

Detector inputs are causal T2 information.

Future max MFE, realized PnL, close reason, and profit-protector outcome are not detector inputs.

## Threshold fitting

Thresholds are derived only from the **Research Discovery TARGET-MFE** distribution.

The primary rule uses the 20th percentile for three causal variables.

Primary T2 veto:

> VETO only if all three are true:

1. **T2 side return <= +0.053541%**
2. **T2 observed MFE - T1 observed MFE <= 0.000000 pp**
3. **T2 trade count - T1 trade count <= 71**

Interpretation:

> weak T2 directional progress  
> AND no favorable-excursion growth from T1 to T2  
> AND weak activity expansion

This is a dead-progression veto, not a future-MFE lookup.

## Why the 20th-percentile rule

Frontier for the same three-feature AND architecture:

| Target percentile | Dropped | BAD-A | BAD-B | GRAY | TARGET | Strong | Dropped PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| 15% | 16 | 7 | 3 | 4 | 2 | 0 | -$12.90 |
| **20%** | **19** | **8** | **5** | **4** | **2** | **0** | **-$19.93** |
| 25% | 22 | 8 | 6 | 4 | 4 | **2** | -$13.02 |
| 30% | 24 | 10 | 6 | 4 | 4 | **2** | -$13.02 |
| 35% | 40 | 14 | 8 | 8 | 10 | **7** | -$27.86 |

The 20th percentile is the last tested point before executable strong winners begin to be removed.

At 25%:

> **2 strong trades are already lost**

Therefore the 20% rule is the high-precision Pareto boundary for this architecture.

## Strict architecture scan

CT-6C also scanned simple interpretable candidates built from the frozen CT-6B T2 feature family:

- two-feature AND rules
- two-of-three rules
- three-of-three rules
- thresholds derived from Research Discovery TARGET percentiles

Strict transport requirements:

- 0 strong dropped
- >=98% overall TARGET selected retention
- >=95% TARGET retention in every chronological block
- vetoed cohort must not create positive net PnL in any block
- must reject BAD trades in both Research and Fresh

Result:

> **only 1 candidate passed all strict gates**

That candidate is the primary three-feature 20th-percentile rule above.

## T2 headline

Baseline T2:

- 383 selected
- 294 executable
- 99 selected strong
- 88 executable strong
- 101 wins
- WR 34.35%
- protected PnL **-$116.80**

After CT-6C primary veto:

- 364 selected
- 281 executable
- 99 selected strong
- **88 executable strong**
- 99 wins
- WR **35.23%**
- protected PnL **-$96.88**

Improvement:

> **+$19.93**

Executable strong retention:

> **88 / 88 = 100%**

## Vetoed cohort

Primary veto flags:

- 19 selected
- 13 executable
- 8 BAD-A
- 5 BAD-B
- 4 GRAY
- 2 TARGET-MFE
- **0 strong**

The two TARGET-MFE flags are:

> **both non-executable**

Therefore:

> **executable TARGET-MFE retention = 100%**

Executable vetoed cohort by label:

### BAD-A

- 8 selected
- 6 executable
- 0 wins
- PnL **-$11.44**

### BAD-B

- 5 selected
- 5 executable
- 0 wins
- PnL **-$11.17**

### GRAY

- 4 selected
- 2 executable
- 2 wins
- PnL **+$2.69**

### TARGET-MFE

- 2 selected
- **0 executable**
- PnL $0

Net vetoed executable PnL:

> **-$19.93**

The GRAY collateral cost is visible, but it is outweighed by BAD-A/B loss removal while strong and executable TARGET remain intact.

## BAD coverage

T2 BAD population:

- BAD total = 127
- BAD-A = 73
- BAD-B = 54

Primary veto removes:

- BAD total: **13 / 127 = 10.24%**
- BAD-A: **8 / 73 = 10.96%**
- BAD-B: **5 / 54 = 9.26%**

Therefore:

> CT-6C is high precision but still low coverage.

It does not solve the full low-MFE problem.

## Research versus Fresh

Research:

- 3 selected vetoed
- 2 executable
- 2 BAD-B
- 1 TARGET-MFE non-executable
- 0 strong
- vetoed PnL **-$2.59**

Fresh:

- 16 selected vetoed
- 11 executable
- 8 BAD-A
- 3 BAD-B
- 4 GRAY
- 1 TARGET-MFE non-executable
- 0 strong
- vetoed PnL **-$17.34**

The rule therefore removes net losses in both Research and Fresh.

## Chronological blocks

| Block | BAD removed | TARGET removed | Strong removed | Vetoed PnL |
|---|---:|---:|---:|---:|
| Research Discovery | 0 | 1 non-exec | 0 | $0.00 |
| Research Validation | 0 | 0 | 0 | $0.00 |
| Research Reserve | 2 | 0 | 0 | **-$2.59** |
| Fresh Oct 1 | 5 | 0 | 0 | **-$8.16** |
| Fresh Oct 2 | 3 | 1 non-exec | 0 | **-$4.84** |
| Fresh Oct 3 | 3 | 0 | 0 | **-$4.34** |

Result:

> 4/6 blocks improve  
> 2/6 neutral  
> 0/6 worsen  
> 0 strong removed in every block

This satisfies the strict CT-6C transport gate.

## Interaction with CT-5B

CT-5B primary removes only T3 entries.

CT-6C primary removes only T2 entries.

Therefore the veto sets are disjoint.

CT-5B result:

- Research: -$126.83
- Fresh: -$229.34
- Combined: **-$356.18**

Adding CT-6C:

- Research: **-$124.25**
- Fresh: **-$212.00**
- Combined: **-$336.25**

Incremental CT-6C improvement:

> **+$19.93**

Total improvement versus original CT-4 +0.075 baseline:

> -$380.39 -> **-$336.25**

or:

> **+$44.14**

Strong retention from the CT-6C layer remains 100%.

## CT-6C verdict

> **PASS as a high-precision T2 low-MFE veto.**

Primary frozen research candidate:

> T2 side return <= +0.053541%
>
> AND T1->T2 observed MFE growth <= 0
>
> AND T1->T2 trade-count growth <= 71
>
> => VETO

Why it passes:

- 0 strong removed
- 0 executable TARGET-MFE removed
- Research improves
- Fresh improves
- no chronological block worsens
- thresholds come from TARGET-side Research Discovery quantiles
- causal inputs only
- simple three-condition logic
- exact protected-PnL improvement +$19.93

Why it is not enough yet:

- only 10.24% of T2 BAD trades are rejected
- most low-MFE loss mass remains
- profitability remains negative after CT-5B + CT-6C

Therefore CT-6C should remain research-only.

## Next engineering implication

The next stage should expand coverage without relaxing the clean core rule blindly.

A sensible CT-6D objective is:

> keep this CT-6C rule frozen as the high-precision core, then search for one or more additional orthogonal T2 BAD veto branches that add meaningful BAD-A/B coverage while preserving strong and executable TARGET retention.

Do not simply move the 20th-percentile rule to 25% or higher, because that already begins deleting strong winners.