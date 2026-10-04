# LP-5B — Operational Winner-vs-Loss Trajectory Anatomy

Status: **PASS — operational trajectory anatomy frozen.**

LP-5B compares the actual outcomes inside the current 454 LONG OPEN cohort:

- **176 realized-positive winners**
- **278 realized non-positive losses**

Unlike LP-1B, LP-5B does **not** use the broader 1,236 universe as the decision population.

## Critical methodological correction

A snapshot is only counted if the trade is still open at that time.

This matters because LP-4 proved that a large number of apparent T+3 loss signals occur after the historical trade has already closed.

Snapshot target times are:
- T+1 = 1 minute after entry
- T+2 = 2 minutes
- T+3 = 3 minutes

The latest fully closed market bar available around those target times is typically about:
- T+1: 0.63 min after entry
- T+2: 1.63 min
- T+3: 2.63 min

## Survivorship / decision availability

| Outcome class | Total N | Alive T+1 | Alive T+2 | Alive T+3 |
|---|---:|---:|---:|---:|
| WIN | 176 | **168 (95.45%)** | **161 (91.48%)** | **156 (88.64%)** |
| ALL LOSS | 278 | 216 (77.70%) | 181 (65.11%) | 161 (57.91%) |
| PRE-0.5 LOSS | 120 | 107 (89.17%) | 89 (74.17%) | 77 (64.17%) |
| WRONG DIRECTION | 96 | 83 (86.46%) | 65 (67.71%) | **53 (55.21%)** |
| STALL LOSS | 24 | 24 (100%) | 24 (100%) | 24 (100%) |
| RIGHT THEN FAILURE | 158 | 109 (68.99%) | 92 (58.23%) | 84 (53.16%) |

This is the central timing tradeoff:

> waiting longer improves separation, but many losses disappear before the decision can act.

For WRONG_DIRECTION specifically:
- 13.54% are gone before T+1
- 32.29% are gone before T+2
- **44.79% are gone before T+3**

Therefore T+3 cannot be the only place to search for a protector.

## Core path trio

LP-5B uses a deliberately simple causal trio for a stable multivariate benchmark:

1. current side return
2. running MFE
3. running MAE

The model is trained only on chronological Discovery and evaluated unchanged on Validation and Reserve.

### All 278 losses vs 176 winners

| Snapshot | D AUC | V AUC | R AUC |
|---|---:|---:|---:|
| T+1 | 0.584 | 0.493 | 0.450 |
| T+2 | 0.612 | 0.592 | 0.673 |
| T+3 | **0.686** | **0.773** | **0.708** |

Generic "all loss" is only moderately distinguishable. Loss protection should therefore be subtype-specific rather than one universal loss rule.

## Pre-0.5 loss vs winners

Population:
- 120 eventual actual losses with historical max MFE < +0.50%
- 176 actual winners

Alive-only core-trio AUC:

| Snapshot | D | V | R |
|---|---:|---:|---:|
| T+1 | 0.650 | 0.587 | 0.589 |
| **T+2** | **0.729** | **0.755** | **0.790** |
| **T+3** | **0.802** | **0.846** | **0.871** |

This is a strong operational signal.

Strong stable single features:

### T+2
Running MFE, lower = worse:
- D 0.704
- V 0.743
- R 0.738

Current side return, lower = worse:
- D 0.714
- V 0.692
- R 0.790

### T+3
Running MFE:
- D **0.791**
- V **0.783**
- R **0.827**

Current side return:
- D **0.761**
- V **0.828**
- R **0.882**

## WRONG_DIRECTION vs winners

Population:
- 96 actual wrong-direction losses
- 176 actual winners

Alive-only core-trio AUC:

| Snapshot | D | V | R |
|---|---:|---:|---:|
| T+1 | 0.665 | 0.591 | 0.582 |
| **T+2** | **0.776** | **0.825** | **0.824** |
| **T+3** | **0.855** | **0.849** | **0.875** |

This is the strongest operationally useful subtype.

Strongest stable single features:

### T+2 current side return
Lower = worse:
- D **0.774**
- V **0.763**
- R **0.816**

### T+2 running MFE
Lower = worse:
- D 0.726
- V 0.793
- R 0.758

### T+3 running MFE
Lower = worse:
- D **0.836**
- V **0.840**
- R **0.848**

### T+3 current side return
Lower = worse:
- D **0.802**
- V **0.827**
- R **0.884**

The distinction is real, but waiting until T+3 loses almost 45% of the original wrong-direction population to prior closure.

## Trajectory medians — alive trades only

### Winners

| Snapshot | Side return | Running MFE | Running MAE |
|---|---:|---:|---:|
| T+1 | +0.086% | +0.229% | -0.129% |
| T+2 | **+0.223%** | **+0.360%** | -0.149% |
| T+3 | **+0.319%** | **+0.476%** | -0.152% |

### Pre-0.5 losses

| Snapshot | Side return | Running MFE | Running MAE |
|---|---:|---:|---:|
| T+1 | +0.030% | +0.169% | -0.110% |
| T+2 | **+0.095%** | **+0.244%** | -0.163% |
| T+3 | **+0.104%** | **+0.302%** | -0.172% |

### Wrong-direction losses

| Snapshot | Side return | Running MFE | Running MAE |
|---|---:|---:|---:|
| T+1 | +0.013% | +0.166% | -0.119% |
| T+2 | **+0.043%** | **+0.228%** | **-0.184%** |
| T+3 | **+0.070%** | **+0.268%** | **-0.195%** |

The major difference is not simply that losses are already deeply red.

Instead, by T+2/T+3 the bad paths show:

> **failure to build favorable excursion and failure to develop positive side return at the same rate as winners.**

That is more useful than a simple MAE stop.

## STALL loss vs winners

There are only 24 actual stall losses.

At T+3 several features look promising:
- 3m side return
- VWAP extension
- selected 5m slope

However Reserve contains only **one** stall loss.

Therefore LP-5B explicitly does **not** claim stable out-of-sample separability for STALL as an independent class.

It can be revisited as part of the broader pre-0.5 lane.

## RIGHT_THEN_FAILURE vs winners

Population:
- 158 right-then-failure losses
- 176 winners

Core-trio AUC:

| Snapshot | D | V | R |
|---|---:|---:|---:|
| T+1 | 0.578 | 0.544 | 0.432 |
| T+2 | 0.541 | 0.443 | 0.595 |
| T+3 | **0.635** | **0.618** | **0.627** |

This remains weak.

The best stable T+3 single feature is current side return:
- D 0.613
- V 0.684
- R 0.647

That is not strong enough to prioritize a dedicated early protector.

## Most important LP-5B finding

The best tradeoff is **not**:

> wait until T+3 because AUC is highest.

Instead:

> **T+2 is already strongly informative for the highest-value loss lanes, while materially more bad trades are still alive.**

For WRONG_DIRECTION:
- T+2 core AUC: 0.776 / 0.825 / 0.824
- 65 / 96 are still alive

For PRE-0.5 LOSS:
- T+2 core AUC: 0.729 / 0.755 / 0.790
- 89 / 120 are still alive

This strongly suggests the next research target is the interval **between T+1 and T+2**, not another fixed T+3 rule.

## LP-5B conclusion

**PASS.**

1. A universal 278-loss protector is too heterogeneous.
2. The economically important **pre-0.5 loss lane is causally distinguishable from winners**, especially by T+2/T+3.
3. **Wrong-direction is even more distinguishable** and is the strongest protector candidate.
4. The useful signal is primarily **slow/failed favorable progress**, not just early MAE.
5. T+3 gives excellent discrimination but is too late for many losses.
6. T+2 offers the best currently observed balance between discrimination and remaining executable population.
7. RIGHT_THEN_FAILURE remains low priority.
8. STALL is too small in Reserve for an independent stable rule claim.

## Next stage

**LP-5C — Raw 5-Second Temporal Anatomy, 1-to-2 Minute Window**

Use Binance archived 5-second path data for the current 454 cohort and ask:

> at 5-second increments between ~60s and ~120s after entry, when does wrong-direction/pre-0.5 separation become strong enough while enough bad trades are still alive?

Required outputs:
- alive population at each 5s timestamp
- D/V/R AUC at each timestamp
- running MFE / current return / drawdown progression
- earliest stable discrimination point
- explicit recovered/winner harm controls

No protector threshold is authorized by LP-5B.
