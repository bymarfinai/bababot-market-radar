# WD-5C VPS Frozen Results — 2026-10-01

Source of truth: VPS `core-prod` frozen 2,175-trade cohort.  
Authority: research only.  
Production rule changes: none.

## Executive result

WD-5C finds that the system does **not** have one generic winner shape.

There are at least three economically distinct phenomena:

1. **true runner opportunity**
2. **small transient opportunity that usually fails**
3. **overheated continuation that looks strongest at entry but is more likely to become a missed runner**

This strongly supports a future multi-head detector rather than a single LONG/SHORT score.

## Opportunity map

| Opportunity tier | Trades | Share | Net PnL | Final positive |
|---|---:|---:|---:|---:|
| **BIG_RUNNER MFE >=2%** | **145** | 6.67% | **+$851.41** | **89.0%** |
| **RUNNER 1–2%** | **378** | 17.38% | **+$323.38** | 72.8% |
| SMALL_EDGE 0.5–1% | 637 | 29.29% | **-$533.39** | 15.1% |
| BORDERLINE 0.35–0.5% | 158 | 7.26% | -$596.98 | 1.9% |
| NO_EDGE <0.35% | 857 | 39.40% | **-$2,383.07** | 0.47% |

The crucial finding is that reaching 0.5–1.0% MFE does **not** imply a high-quality opportunity.

The SMALL_EDGE group is large but economically negative.

## Big runner anatomy

The 145 BIG_RUNNER trades have:

- median MFE: **+2.739%**
- median realized PnL: **+0.903%**
- median MAE: **-0.955%**
- median duration: **36.7 min**
- median time to first +0.5% MFE: **7.79 min**
- median capture ratio: **33.1%**

Path composition:

| Path | Trades | Share of BIG_RUNNER |
|---|---:|---:|
| **RECOVERED_WINNER** | **97** | **66.9%** |
| CLEAN_WINNER | 32 | 22.1% |
| MISSED_OPPORTUNITY | 16 | 11.0% |

This means most big runners are **not clean straight-line winners**.

## Winner path finding

Across all profitable WD-1 winner paths:

- CLEAN_WINNER: 115
- RECOVERED_WINNER: 385

So most meaningful winners are recovered winners.

### Big realized wins

63 trades realized >= +1%.

- median MFE: **+3.821%**
- median realized: **+1.488%**
- median MAE: **-0.910%**
- median duration: **62.2 min**
- CLEAN: 18
- RECOVERED: **45**

Therefore **71.4% of big realized winners are recovered-drawdown winners**.

This is a critical constraint for future early-loss guards.

## Capture efficiency

For trades that reached at least +0.5% MFE:

| Capture class | Trades | Net PnL | Median MFE | Median realized |
|---|---:|---:|---:|---:|
| HIGH_CAPTURE >=50% | 26 | +$342.48 | 2.777% | 1.583% |
| MEDIUM_CAPTURE 25–50% | 219 | **+$811.09** | 1.622% | 0.538% |
| LOW_CAPTURE <25% | 255 | +$234.27 | 1.142% | 0.132% |
| **MISSED** | **660** | **-$746.44** | 0.703% | -0.172% |

Only 26 trades captured at least half of their MFE.

The system is therefore leaving substantial opportunity uncaptured even among winners.

## Key finding — runner winners are often LESS extreme at entry

The strongest WD-5C result is the difference between runner winners and runner misses.

### Ordinary runner: 1–2% MFE

275 winners vs 103 misses.

Median entry values:

| Feature | Winner | Missed |
|---|---:|---:|
| selected score | **80.53** | **88.59** |
| 5m selected-side return | **0.793%** | **1.318%** |
| 15m selected-side return | **1.098%** | **1.958%** |
| 1h selected-side return | **1.782%** | **2.569%** |
| 3m side return at gate | **0.520%** | **0.805%** |
| range ratio | **2.41x** | **3.19x** |
| selected-side taker share | **0.646** | **0.569** |

Missed runners therefore tended to look **more explosive / more extended** but had weaker near-entry taker support.

This pattern is stable enough across chronological blocks to be taken seriously as an exhaustion/overheat hypothesis.

### Big runner: >=2% MFE

129 winners vs 16 misses.

The same pattern becomes extreme:

| Feature | Winner | Missed |
|---|---:|---:|
| selected score | **82.31** | **92.98** |
| 5m selected-side return | **0.868%** | **2.286%** |
| 15m selected-side return | **1.235%** | **2.387%** |
| range ratio | **2.47x** | **7.60x** |
| trades ratio | **2.53x** | **6.24x** |
| volume ratio | **3.58x** | **18.18x** |
| gate side-adjusted drift | **-0.031%** | **-0.257%** |

Sample size for missed BIG_RUNNER is only 16, so this table is directional evidence, not a production threshold.

But it independently reinforces the 1–2% runner result.

## Big runner vs small edge

Pre-entry separation between BIG_RUNNER and SMALL_EDGE exists, but is modest.

Big runners tend to show:

- somewhat stronger 5m/1h selected-side momentum,
- stronger 3m gate move,
- somewhat higher OI change,
- slightly higher baseline volatility,
- lower impulse concentration,
- somewhat different Stage11C evidence-family combinations.

No single entry feature cleanly separates the two.

This suggests runner-size prediction should likely be probabilistic / multi-feature rather than one hard threshold.

## Big runner vs no edge

Separation is clearer than BIG_RUNNER vs SMALL_EDGE.

Big runners tend to have:

- stronger selected-side 5m / 15m / 1h momentum,
- stronger selected momentum component,
- somewhat higher selected score,
- larger movement activity,
- meaningful but not necessarily extreme expansion,
- different Stage11C family combinations.

So detecting "runner-worthy opportunity versus no edge" appears more feasible than predicting exact runner magnitude.

## Clean vs recovered winner

CLEAN and RECOVERED winners are materially different entry-path archetypes.

Recovered winners are not simply poor versions of clean winners.

They differ in:

- near-entry taker alignment,
- 1m micro return behavior,
- range/trade expansion,
- selected score / score edge,
- gate drift,
- Stage11C family combination.

This confirms a future detector should explicitly predict **expected path shape**, not only direction.

## Composite archetypes

Largest classes:

| Composite | Trades | Net PnL |
|---|---:|---:|
| NO_EDGE_NONWIN | 853 | -$2,384.05 |
| SMALL_EDGE_FAILED | 541 | -$569.91 |
| RUNNER_RECOVERED | 219 | +$362.24 |
| BORDERLINE_NONWIN | 155 | -$598.09 |
| RUNNER_MISSED | 103 | -$132.16 |
| BIG_RUNNER_RECOVERED | 97 | **+$672.08** |
| SMALL_EDGE_WIN | 96 | +$36.52 |
| RUNNER_CLEAN | 56 | +$93.30 |
| BIG_RUNNER_CLEAN | 32 | +$223.71 |
| BIG_RUNNER_MISSED | 16 | -$44.37 |

## Architectural implication

WD-5C supports a future detector with separate heads:

### 1. Opportunity-size head

Predict:

- BIG_RUNNER
- RUNNER
- SMALL_EDGE
- NO EDGE

### 2. Path-shape head

Predict:

- CLEAN
- RECOVERED / temporary drawdown expected
- OVERHEATED / exhaustion risk

### 3. Direction thesis head

Compare:

- continuation LONG
- continuation SHORT
- reversal LONG
- reversal SHORT

### 4. Capture-policy head

Use the predicted archetype to choose profit-protection behavior.

For example:

- high runner probability + recovered-path profile -> looser early protection
- small-edge profile -> protect aggressively
- overheat/exhaustion profile -> avoid continuation / evaluate reversal

## Formal WD-5C conclusion

The most important insight is:

> **The strongest-looking continuation is not necessarily the best runner.**

Runner misses frequently enter with higher momentum, score, range, volume, and trade expansion than runner winners.

The system therefore needs to learn the distinction between:

> **healthy expansion**

and

> **overheated / exhausted expansion**

This is directly complementary to the opposite-thesis information gap discovered in WD-5B.

## Next handoff

WD-5D should focus on **Opportunity + Exhaustion Feature Discovery**.

The highest-priority tasks are:

1. construct causal overextension / momentum-decay features,
2. model BIG/RUNNER opportunity versus SMALL/NO EDGE,
3. model runner winner versus runner miss,
4. model clean versus recovered path expectation,
5. integrate these signals with the missing reversal thesis from WD-5B.

The goal is not yet a production rule. It is to build the richer feature space required for a multi-head Opportunity Detector.
