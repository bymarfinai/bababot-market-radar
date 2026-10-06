# SHORT-SA3 — Hybrid Admission Recomposition + Positive Temporal Rescue

Status: **PASS research candidate / 95% strong retention restored / NOT runtime-ready**

## Objective

SA-3 tests whether the SA-2 Opportunity Quality Gate can be integrated without simply stacking more permanent kills.

Frozen upstream/downstream assumptions:

- CT5B and CT6C remain hard vetoes.
- SA2 Q95 is the primary Opportunity Quality Gate.
- CT7C remains useful because Q95 cannot replace its failure coverage.
- T is used only as a positive rescue / confirmation mechanism.
- Profit Protector remains frozen at V4.3 SHORT-LS4 + BE0.10.
- No runtime or paper-entry rule is changed.

The target is:

> materially improve PnL versus the current CT7 stack while restoring combined executable strong retention to at least 95%.

## Architecture comparison before rescue redesign

### Current CT7 stack

CT5B + CT6C + CT7C + CT7D CLEAN2:

- executable: **794**
- WR: **36.78%**
- executable strong: **238 / 246 = 96.75%**
- PnL: **-$136.32**

### Q95 replacing CT7C

CT5B + CT6C + Q95:

- executable: 813
- executable strong: 233 / 246 = 94.72%
- PnL: **-$189.72**

Verdict:

> **REJECT replacement.**

Q95 cannot replace CT7C because CT7C removes a large failure population that Q95 does not cover.

### Q95 stacked with CT7C, no positive rescue

CT5B + CT6C + CT7C + Q95:

- executable: 730
- WR: 37.81%
- executable strong: **226 / 246 = 91.87%**
- PnL: **-$69.49**

Economically much better, but strong collateral is unacceptable.

### Q95 + CT7C + old CLEAN2 only

- executable: 732
- WR: 37.98%
- executable strong: 228 / 246 = 92.68%
- PnL: **-$67.40**

CLEAN2 alone is not enough to restore the strong-retention guardrail.

## Rescue search contract

Rescue is allowed only for trades flagged by:

> Q95 OR CT7C

and not already hard-vetoed by:

> CT5B OR CT6C.

Thresholds are fit from **Research Discovery strong-trade quantiles**.

Future MFE is not used as a live input.

Realized PnL is not used to form thresholds.

T1 was rejected because positive rescue precision was too low.

T2/T3 rule families were evaluated for:

- strong coverage inside the negative-union set;
- non-strong collateral;
- full Research Discovery / Research Holdout / Fresh strong-vs-BAD transport;
- exact delayed-entry economics.

## Broad rescue attempts

A single T2/T3 rule wide enough to restore >=95% strong retention re-admitted too many non-strong trades.

Examples:

- 8 strong + 9 non-strong rescue -> exact rescue PnL **-$11.62**
- 9 strong + 10 non-strong rescue -> still economically contaminated
- broad CT7D-style rescue behavior therefore remains rejected.

This reproduces the earlier lesson:

> positive temporal rescue must be multi-branch and selective.

## SA-3 primary rescue branches

The final research candidate uses four branches with earliest causal horizon winning.

### A1 — T3 MFE / taker / VWAP rescue

At least **2 of 3**:

- d3 confirm MFE >= **0.24341195**
- T3 selected taker share >= **0.65706536**
- T3 delta selected VWAP extension >= **0.24927205**

Threshold family: Research Discovery strong Q70.

### A2 — T3 strong continuation rescue

At least **3 of 4**:

- T3 observed MFE >= **0.72023495**
- d3 confirm trades >= **417.2**
- T3 delta coin-minus-market 15m >= **0.22163414**
- T3 micro decay <= **0.09472091**

Threshold family: Research Discovery strong Q60.

### A3 — T2 participation / excursion growth rescue

All **3 of 3**:

- d2 confirm MFE >= **0.03920019**
- d2 confirm trades >= **216**
- T2 delta selected VWAP extension >= **0.01907934**

Threshold family: Research Discovery strong Q50.

### M1 — marginal T2 strong recovery

At least **2 of 3**:

- d2 confirm side return >= **0.26943572**
- T2 selected taker share >= **0.68738986**
- T2 delta selected VWAP extension >= **0.21796914**

Threshold family: Research Discovery strong Q80.

M1 was chosen as the minimum-collateral marginal branch that added one new strong candidate at the earlier T2 horizon; exact PnL was used only as validation.

## Exact delayed-entry replay

Every rescued trade enters only after the complete T2/T3 confirmation bar.

Execution is replayed with:

- exact Binance 1m open after the target bar;
- exact aggTrade path;
- frozen V4.3 SHORT-LS4;
- BE0.10;
- unchanged fee/slippage/notional;
- unchanged historical close boundary.

## Primary result

SA-3 primary:

- executable: **744**
- wins: **284**
- WR: **38.17%**
- executable strong: **234 / 246**
- strong retention: **95.12%**
- executable TARGET >=1%: **266 / 279**
- TARGET retention: **95.34%**
- PnL: **-$67.09**

Versus current CT7 stack:

> **-$136.32 -> -$67.09**

Improvement:

> **+$69.22**

WR:

> **36.78% -> 38.17%**

The system remains negative, but approximately half of the current residual loss magnitude is removed while satisfying the 95% strong-retention guardrail.

## Rescue cohort economics

Exact rescued executable trades:

- total: **14**
- strong: **8**
- non-strong: **6**
- wins: **8**
- rescue PnL: **+$2.3920**

Strong rescue PnL:

> **+$18.3638**

Non-strong rescue PnL:

> **-$15.9718**

The positive selector therefore pays for its collateral at the frozen exact-replay level.

This is materially better than the broad rescue variants whose rescue cohort was net negative.

## Chronological stability versus current CT7 stack

| Block | Current PnL | SA-3 PnL | Delta |
|---|---:|---:|---:|
| Research Discovery | -$41.28 | **-$26.37** | **+$14.91** |
| Research Validation | +$17.00 | **+$17.35** | **+$0.35** |
| Research Reserve | -$5.35 | **+$2.83** | **+$8.18** |
| Fresh Oct 1 | -$121.66 | **-$113.99** | **+$7.66** |
| Fresh Oct 2 | +$96.18 | **+$110.00** | **+$13.82** |
| Fresh Oct 3 | -$81.21 | **-$56.91** | **+$24.30** |

Result:

> **6 / 6 blocks improve versus the current frozen CT7 stack.**

Strong count is lower in some blocks, but the aggregate retention remains above 95%.

## Research / Fresh

SA-3 primary:

### Research

- executable: 235
- wins: 93
- WR: 39.57%
- executable strong: 74
- PnL: **-$6.19**

### Fresh

- executable: 509
- wins: 191
- WR: 37.52%
- executable strong: 160
- PnL: **-$60.91**

Both remain negative, so SA-3 is not a profitability solution.

However the improvement is not isolated to one chronological block.

## Remaining MFE anatomy after SA-3

| Bucket | Exec | WR | PnL |
|---|---:|---:|---:|
| BAD-A <0.30% | 132 | 0.00% | **-$271.04** |
| BAD-B 0.30-0.50% | 102 | 2.94% | **-$232.64** |
| GRAY 0.50-1.00% | 244 | 25.82% | **-$127.63** |
| TARGET >=1.00% | 266 | 81.95% | **+$564.21** |

The core problem remains unchanged:

> low-MFE BAD trades still dominate the negative side.

SA-3 improves admission quality and strong preservation, but does not eliminate the residual BAD population.

## Final architecture implication

The best tested SA-3 design is not:

> Q95 replaces CT7C

and not:

> Q95 permanently kills everything it flags.

It is:

> candidate SHORT  
> -> CT5B / CT6C hard veto  
> -> Q95 Opportunity Quality + CT7C negative union  
> -> if unflagged: continue normal path  
> -> if flagged: allow only selective T2/T3 positive rescue  
> -> entry  
> -> frozen Profit Protector

This separates three jobs cleanly:

1. **Opportunity Quality / CT7C** = negative selection
2. **T2/T3** = positive strong confirmation / rescue
3. **Profit Protector** = lifecycle economics

## SA-3 verdict

> **PASS as the primary research architecture.**

Reasons:

- Q95 adds material loss removal not duplicated by CT7C.
- CT7C cannot be removed.
- selective T rescue restores strong retention to **95.12%**.
- TARGET retention remains **95.34%**.
- exact rescue cohort is net positive.
- PnL improves by **+$69.22** versus current.
- **6/6** chronological blocks improve versus current.

But:

- total PnL is still **-$67.09**;
- Research and Fresh are both still negative;
- rescue branch selection has now been researched on all currently available cohorts;
- no runtime authority is granted.

## Recommended next stage

The next stage should be:

> **SA-4 — Full Admission Re-run / residual BAD audit under the new ordering**

SA-4 should treat SA-3 as the candidate SHORT admission architecture and recompute:

- how many original BAD-A/B never reach T;
- how many are rescued;
- residual BAD fallback anatomy;
- whether CT7F-style conditional expansion is still needed;
- final exact replay versus current architecture;
- sealed/unseen validation requirements before any paper promotion.

No runtime promotion is authorized by SA-3.