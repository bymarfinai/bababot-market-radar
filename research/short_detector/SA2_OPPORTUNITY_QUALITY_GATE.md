# SHORT-SA2 — Opportunity Quality Gate Development

Status: **PASS research architecture / conservative gate family found / NOT runtime-ready**

## Objective

SA-2 redesigns SHORT admission quality without changing Stage 5 directional context, temporal confirmation, or Profit Protector.

The problem from SA-1 is:

> a coin can look extremely strong relative to its own quiet baseline while still having insufficient absolute excursion quality.

SA-2 therefore tests a separate Opportunity Quality Gate using causal pre-T dimensions rather than simply raising Stage 4 score.

No runtime or paper-entry rule is changed.

## Feature basis

The scan prioritizes six pre-T quality dimensions:

1. absolute selected-side 1h displacement
2. prior median absolute 5m movement amplitude
3. absolute 5m quote liquidity
4. coin-minus-market 30m displacement
5. coin residual versus BTC 5m
6. distance from selected extreme 15m

Thresholds are fitted only from Research Discovery TARGET-MFE quantiles.

Future MFE is used only as an outcome label.

Realized PnL is evaluation only.

## Core finding — safe global hard-gate coverage has a natural ceiling

A broad global gate cannot remove 40–60% of BAD while preserving strong winners.

Best observed frontier:

| Approx BAD rejection | TARGET retention | Strong retention |
|---|---:|---:|
| **16.6%** | **96.6%** | **96.2%** |
| 25.6% | 92.9% | 92.5% |
| 36.2% | 87.1% | 86.1% |
| 45.5% | 80.1% | 78.2% |
| 55.5% | 71.2% | 68.4% |

Therefore the original 40–60% BAD rejection ambition is not safe as a single global hard gate.

The measured ceilings are approximately:

> **97% TARGET + 97% strong retention -> ~13.1% BAD rejection**

and

> **95% TARGET + 95% strong retention -> ~18.3% BAD rejection**

This is a major SA-2 conclusion.

## Q97 safety comparator

### Q97_MAX

Reject only when all three are weak:

1. prior median abs 5m return <= **0.1298166%**
2. quote volume 5m <= **28,174.784**
3. coin-minus-market 30m <= **0.9372983**

Threshold origins:

- TARGET Research Discovery Q15
- TARGET Research Discovery Q20
- TARGET Research Discovery Q40

Result:

- rejected selected: 68
- BAD rejected: **52 / 398 = 13.1%**
- TARGET retention: **97.55%**
- strong retention: **97.37%**

Research/Fresh BAD rejection:

- Research: 9.8%
- Fresh: 14.5%

Standalone CT4 rejected executable cohort:

> **-$91.16**

If mechanically stacked on the current CT5B+CT6C+CT7C+CT7D system:

- current PnL: -$136.32
- diagnostic post-gate PnL: **-$86.62**
- executable: 755
- wins: 285
- WR: **37.75%**
- executable strong: 233

This stacking result is diagnostic only.

One known block, Research Validation, would lose a net-positive +$2.31 cohort, so Q97 is not automatically production-safe despite high aggregate retention.

## Q95 primary research candidate

### Q95_AGGRESSIVE

Reject only when all three are weak:

1. selected-side 1h return <= **1.2273333%**
2. quote volume 5m <= **28,174.784**
3. coin-minus-market 30m <= **0.8913809**

Threshold origins:

- TARGET Research Discovery Q30
- TARGET Research Discovery Q20
- TARGET Research Discovery Q35

Interpretation:

> weak absolute 1h displacement + low absolute liquidity + weak market-relative displacement.

This directly attacks the SA-1 normalization loophole.

Result:

- rejected selected: **105**
- BAD rejected: **73 / 398 = 18.34%**
- TARGET rejected: 15 / 326
- TARGET retention: **95.40%**
- strong rejected: 13 / 266
- strong retention: **95.11%**

Research/Fresh transport:

- Research BAD rejection: 19.5%
- Fresh BAD rejection: 17.8%
- Research TARGET retention: 94.9%
- Fresh TARGET retention: 95.6%
- Research strong retention: 95.2%
- Fresh strong retention: 95.1%

So the gate transports very evenly by source.

## Economic validation

Q95 standalone against CT4 +0.075 baseline:

- 102 rejected executable trades
- 18 historical winners inside rejected cohort
- rejected cohort protected PnL: **-$152.52**
- CT4 keep PnL improves from -$380.39 to **-$227.87**

This does not make the detector profitable by itself, but it removes a materially negative admission cohort.

### Current-stack diagnostic

If Q95 is mechanically stacked after the current CT5B+CT6C+CT7C+CT7D research stack:

- removed current executable: 62
- removed wins: 14
- removed strong: 10
- removed PnL: **-$68.92**

Diagnostic result:

- PnL: **-$136.32 -> -$67.40**
- executable: 732
- wins: 278
- WR: **37.98%**
- executable strong: **228**

Current-stack removed PnL is negative in all six chronological blocks.

However:

> 228 / 246 baseline executable strong = only **92.7% combined strong retention**.

Therefore direct stacking is **rejected as a deployment architecture**.

## Why >=30% BAD rejection is rejected

At ~25.6% BAD rejection:

> strong retention is already only **92.5%**.

At ~36% BAD rejection:

> strong retention falls to **86.1%**.

At ~45%:

> **78.2%**.

At ~55%:

> **68.4%**.

So the data does not support one aggressive global Opportunity Quality Gate.

The bad population overlaps too much with valid strong opportunity morphology once the gate is widened.

## SA-2 verdict

> **PASS as an opportunity-quality architecture and research gate family.**

The SA-1 hypothesis is confirmed:

> SHORT admission should explicitly distinguish abnormal movement from tradeable opportunity quality.

But SA-2 also proves:

> a single global quality gate should remain conservative.

Frozen research points:

- **Q97_MAX** = high-retention safety comparator
- **Q95_AGGRESSIVE** = primary research candidate for the next stage
- >=30% global BAD rejection = rejected due excessive winner collateral

Q95 is not authorized for runtime.

## Next stage — SA-3

SA-3 should not simply stack Q95 on CT-7C.

It should test:

1. whether Q95 can **replace** overlapping CT-7C kill branches;
2. whether T/positive confirmation can rescue strong/TARGET trades inside Q95;
3. combined strong retention target >=95–97%;
4. exact execution-realistic replay after the new ordering;
5. Research/Fresh and chronological stability.

Desired architecture:

> Movement detection
> -> Opportunity Quality Gate
> -> directional context
> -> T positive confirmation / rescue
> -> entry
> -> Profit Protector

No runtime promotion is authorized by SA-2.
