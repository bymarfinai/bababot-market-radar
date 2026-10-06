# LQ-3B — Breakout Acceptance + Retest Gate

Status: **PRECISION SIGNAL FOUND / PRODUCTION HOLD**

Version: `lq3b-breakout-acceptance-retest-v1`

## Objective

LQ-3A established two distinct states for LONG entries that start inside a **FRESH 15m supply** zone:

- rejection below the lower boundary is strongly adverse;
- trading above the upper boundary is a possible continuation state, but immediate breakout entry risks chasing.

LQ-3B therefore tests the causal sequence:

> fresh 15m supply -> break upper -> hold above -> pullback/retest -> retest holds -> reclaim -> fresh LONG entry.

The goal is not to replace the main LONG detector. It is to determine whether a **rescue / acceptance route** exists for the small subset of fresh-supply trades that genuinely break through.

No production order authority is changed.

## Frozen cohort

Exact LQ-3A cohort:

- total: **102**
- GOOD = Recovered + Correct Runner: **19**
- BAD = Wrong Direction + Stall: **68**
- RTF: **15**
- TRAIN / VALIDATION / RESERVE = **58 / 22 / 22**

Raw path coverage:

- Binance Vision USD-M daily aggTrades
- **102 / 102** non-empty raw paths
- archive errors: **0**

## Exact replay contract

A candidate must complete all states causally.

1. Break the old 15m supply upper boundary.
2. Breakout must occur within **5 minutes** of the original entry.
3. Price must remain accepted for a short hold period.
4. Do **not** buy the breakout.
5. Wait for price to return toward the broken upper boundary.
6. The retest must not structurally fail through the lower boundary.
7. Require a small reclaim from the retest low.
8. Only then create a fresh LONG entry.
9. Apply fee = 0.05% per side and slippage = 2 bps per side.
10. No TP; fresh SL grid = 0.30 / 0.40 / 0.50%.
11. If SL is not hit, exit at the original historical close.

Coarse grid:

- breakout buffer: 0.00 / 0.05 / 0.10%
- acceptance hold: 15 / 30 / 60s
- retest band above upper edge: 0.05 / 0.10 / 0.15%
- retest hold: 15 / 30s
- reclaim: 0.03 / 0.05 / 0.10%
- SL: 0.30 / 0.40 / 0.50%
- total cells: **486**

Threshold choice is TRAIN-only. Validation and Reserve are not used for selection.

## Main result

The route is **high precision but very sparse**.

Maximum TRAIN entries in any grid cell:

> **7**

Therefore no cell satisfies the preregistered minimum of 8 TRAIN entries.

So LQ-3B does **not** freeze a production candidate and does not name a valid "best" parameter set.

This is intentional. Small-sample positive economics are reported descriptively, not promoted.

## Representative central rule

To understand the state transition without cherry-picking the highest-PnL cell, use a central rule from the preregistered grid:

- break buffer: **+0.05%**
- breakout hold: **15s**
- retest: within **+0.10%** of old supply upper
- retest hold: **15s**
- reclaim: **+0.03%**
- acceptance wiggle: 0.03%
- structural retest lower tolerance: 0.03%

This rule is illustrative / representative, not production-selected.

### Funnel

| State | N | GOOD | BAD | RTF |
|---|---:|---:|---:|---:|
| Fresh 15m supply base | **102** | 19 | 68 | 15 |
| Cross upper +0.05% | **24** | 11 | 4 | 9 |
| Accepted / held 15s | **12** | 7 | 2 | 3 |
| Returned to retest band | **11** | 6 | 2 | 3 |
| Retest structurally held | **10** | 6 | 2 | 2 |
| Reclaimed | **9** | **6** | **1** | 2 |

Among classified GOOD/BAD examples, the final reclaim state is:

> **6 GOOD / 1 BAD = 85.7% GOOD**

Compare with the original fresh-supply cohort:

> 19 GOOD / 68 BAD = 21.8% GOOD among classified examples.

The supply map is therefore useful as a **state machine**, not merely as a static entry-distance feature.

## Representative exact economics

### SL 0.30%

| Split | Entries | WR | Net PnL | PF |
|---|---:|---:|---:|---:|
| TRAIN | 7 | 57.14% | **+$4.96** | 2.036 |
| VALIDATION | 1 | 100% | **+$5.50** | — |
| RESERVE | 1 | **0%** | **-$2.26** | 0 |
| ALL | 9 | **55.56%** | **+$8.20** | **2.163** |

ALL sample:
- median time to fresh entry: **117.1s**
- median post-entry MFE: **0.757%**
- post-entry MFE >=0.5%: **66.67%**
- post-entry MFE >=1%: **44.44%**
- class mix: 2 Correct Runner, 4 Recovered, 2 RTF, 1 Wrong Direction.

### SL robustness

Same 9-entry structural route:

| SL | TRAIN PnL | ALL PnL | ALL WR | ALL PF |
|---|---:|---:|---:|---:|
| 0.30% | +$4.96 | **+$8.20** | 55.56% | 2.163 |
| 0.40% | +$4.57 | **+$6.92** | 55.56% | 1.831 |
| 0.50% | +$3.98 | **+$7.22** | 55.56% | 1.900 |

Economics remain positive across all three tested stop widths, but the sample is far too small to infer transportability.

## Parameter-family stability

The result is not isolated to exactly one parameter tuple.

At SL 0.30%, **48 neighboring structural parameter combinations** produced:
- at least 8 total entries,
- at least 5 GOOD,
- no more than 2 BAD.

Examples around:
- breakout buffer 0.05–0.10%
- 15s acceptance hold
- retest 0.10–0.15%
- reclaim 0.03–0.05%

repeatedly produced 8–10 entries dominated by GOOD / RTF rather than BAD.

However, this does **not** solve the OOS problem.

## Why production is HOLD

The apparent precision is real enough to continue studying, but transport evidence is not sufficient.

For the representative rule:

- TRAIN entries: 7
- VALIDATION entries: 1
- RESERVE entries: **1**

The only Reserve trade is RTF and loses.

Across the full 486-cell grid:

> **0 cells are positive in TRAIN + VALIDATION + RESERVE simultaneously.**

The strongest all-history cells are even smaller. One 5-entry cell shows 80% WR and +$10.64, but has **zero Reserve entries**. It is ignored as non-transportable.

Therefore:

> LQ-3B is a precision discovery, not a deployable strategy.

## What this says about the original entry problem

The problem is not simply:

> "signal LONG is wrong."

Inside fresh 15m supply:

1. Most candidates never produce a valid breakout.
2. Some cross the upper boundary but do not establish acceptance.
3. A very small subset breaks, holds, retests, and reclaims.
4. That final subset is heavily enriched in genuine winners.

This supports changing the interpretation of fresh 15m supply from:

> HARD BLOCK

to:

> **WAIT / REQUIRE PROOF**

and then routing the state:

```
LONG candidate inside FRESH 15m supply
              |
              +-- falls below lower boundary
              |      -> REJECTED
              |      -> abort / early-exit candidate (LQ-3A)
              |
              +-- remains inside
              |      -> UNRESOLVED / WAIT
              |
              +-- breaks upper
                     |
                     +-- no acceptance / failed retest
                     |      -> DO NOT CHASE
                     |
                     +-- hold + retest + reclaim
                            -> ACCEPTED BREAKOUT
                            -> precision LONG candidate
```

## Practical verdict

### Area to avoid

The strongest negative structural state remains:

> **fresh 15m supply + rejection through the lower boundary at T+2/T+3.**

LQ-3A showed that state has near-zero useful runner probability.

### Area with higher apparent win probability

The most promising positive structural state currently is:

> **fresh 15m supply -> accepted breakout -> retest hold -> reclaim.**

It is materially enriched in winners and shows positive exact economics in the small available sample.

But it is too rare to become the only LONG route and too sparse in Reserve to call production-ready.

## Next research direction

The next high-value stage should move to the **large complement**, not keep squeezing the 102-trade fresh-supply subset.

Recommended:

**LQ-3C — Open-Lane / Outside-Fresh-Supply Anatomy**

Question:

> Among the 1,134 LONGs that are *not* inside fresh 15m supply, which structural locations contain the highest concentration of real runners and the lowest concentration of low-MFE failures?

This is where a higher-coverage positive admission rule is more likely to exist.

LQ-3B should remain available as a **special breakout-rescue route** for fresh-supply candidates, pending larger forward evidence.
