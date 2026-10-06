# LQ-3A — Fresh 15m Supply Winner vs Failure Anatomy

Status: **PASS — REJECTION STATE FOUND / ACCEPTANCE STILL RESEARCH**

Version: `lq3a-fresh15m-supply-anatomy-v1`

## Objective

LQ-2 found one adverse structural location for LONG:

> entry inside a **FRESH 15m supply** zone.

LQ-3A asks the next question:

> Why do some LONGs survive this zone while most fail?

The stage is deliberately anatomy-only. It does **not** optimize or deploy a production block.

## Frozen cohort

Exact LQ-2 cohort:

- Total: **102**
- TRUE_WRONG_DIRECTION: **58**
- STALL_NO_EDGE: **10**
- RIGHT_THEN_FAILURE: **15**
- RECOVERED_DRAWDOWN: **16**
- CORRECT_RUNNER: **3**

For GOOD-vs-BAD discrimination:

- **BAD = WD + STALL = 68**
- **GOOD = RECOVERED + CORRECT = 19**
- **RTF = 15**, held out as ambiguous / secondary

Chronological split remains:

- TRAIN: 58
- VALIDATION: 22
- RESERVE: 22

Stage11C gate-to-fill latency is tiny relative to the 1–3 minute checkpoints:

- median: **198 ms**
- p90: **294 ms**
- max: **797 ms**

Temporal checkpoints use the original frozen Stage11C `gate_current_price` anchor, matching the WD5H temporal feature contract.

## Entry-time geometry: useful context, not enough by itself

| Geometry | GOOD median | BAD median | Interpretation |
|---|---:|---:|---|
| Penetration into 15m supply | **0.409** | 0.284 | winners tend to enter deeper in the zone |
| Room to upper edge | **0.184%** | 0.320% | winners tend to already be closer to breakout boundary |
| Zone volume ratio | **2.09x** | 1.42x | winners occur in somewhat stronger-volume bases |
| Zone age | **636 min** | 238 min | winner zones are older in this sample |
| Departure strength | 1.34 ATR | **1.58 ATR** | stronger original departure does not imply winner |
| Zone width | 0.463 ATR | 0.505 ATR | weak separation |

Static zone geometry is therefore insufficient for a hard entry rule.

The strongest entry-time structural feature is penetration depth, but its GOOD-vs-BAD AUC is only about **0.639**.

## Temporal discrimination dominates static geometry

Top preselected features by GOOD-vs-BAD univariate separation:

| Feature | Separation AUC | Direction |
|---|---:|---|
| **T+3 side return** | **0.815** | higher = GOOD |
| **T+2 side return** | **0.755** | higher = GOOD |
| T+3 selected slope5 | 0.741 | higher = GOOD |
| T+2 selected candle body | 0.739 | higher = GOOD |
| T+2 selected taker share | 0.710 | higher = GOOD |
| T+2 selected CLV | 0.707 | higher = GOOD |
| Entry selected slope5 | 0.701 | lower = GOOD |
| Entry VWAP extension | 0.698 | lower = GOOD |
| Entry gate 3m side return | 0.694 | lower = GOOD |
| Entry penetration fraction | 0.639 | higher = GOOD |

Interpretation:

The winners are not simply the LONGs with the strongest initial impulse.

Inside fresh supply, winning trades tend to be **less overextended at entry**, then prove themselves through subsequent price / flow acceptance.

## Zone-state transition

For every trade, the frozen temporal checkpoint price is compared with the original fresh 15m supply boundaries.

State:

- `BELOW` = price has rejected through the lower boundary
- `INSIDE` = price remains inside supply
- `ABOVE` = price is trading above the upper boundary

### T+1

| State | N | Win rate | MFE >=1% |
|---|---:|---:|---:|
| BELOW | 31 | 9.68% | 6.45% |
| INSIDE | 67 | 20.90% | 19.40% |
| ABOVE | 4 | 50.00% | 50.00% |

T+1 already contains information, but sample sizes are still weak.

### T+2

| State | N | BAD | GOOD | RTF | Win rate | MFE >=1% |
|---|---:|---:|---:|---:|---:|---:|
| **BELOW** | **42** | **36** | **2** | 4 | **4.76%** | **2.38%** |
| INSIDE | 48 | 29 | 12 | 7 | 25.00% | 22.92% |
| ABOVE | 12 | 3 | 5 | 4 | 41.67% | 41.67% |

Among classified GOOD/BAD trades, T+2 BELOW is:

> **94.74% BAD**

Chronological T+2 BELOW:

- TRAIN: 21 trades, 4.8% realized win
- VALIDATION: 9 trades, **0% win**
- RESERVE: 12 trades, **8.3% win**
- Reserve MFE >=1%: **0%**

This is the earliest strong rejection state found in LQ-3A.

### T+3

| State | N | BAD | GOOD | RTF | Win rate | MFE >=1% | PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| **BELOW** | **45** | **39** | **1** | 5 | **2.22%** | **2.22%** | **-$131.26** |
| INSIDE | 42 | 26 | 11 | 5 | 26.19% | 23.81% | -$59.61 |
| **ABOVE** | **15** | 3 | **7** | 5 | **46.67%** | **40.00%** | **+$11.93** |

Among classified GOOD/BAD trades:

- T+3 BELOW = **97.5% BAD**
- T+3 ABOVE = **70.0% GOOD**

This creates a very interpretable three-state map.

## Strong negative state: rejection below supply

### T+3 BELOW lower boundary

This is the strongest LQ-3A result.

Composition:

- TRUE_WRONG_DIRECTION: **34**
- STALL: **5**
- RTF: 5
- RECOVERED: **1**
- CORRECT_RUNNER: **0**

Metrics:

- 45 trades
- realized win rate: **2.22%**
- MFE >=1%: **2.22%**
- median final MFE: **0.190%**
- historical PnL: **-$131.26**

Chronological:

- TRAIN: **0% win**
- VALIDATION: **7.7% win**
- RESERVE: **0% win**

Reserve composition contains **0 GOOD**.

### Interpretation

For a LONG that entered inside fresh 15m supply:

> if price has fallen through the zone's lower boundary by T+2/T+3, the market has not merely failed to break supply — it has shown a causal rejection of the LONG thesis.

This is substantially more specific than:

> inside supply = bad.

## Positive state: above supply

T+3 ABOVE upper boundary is materially enriched in winners:

- 15 trades
- GOOD: **7**
- BAD: 3
- RTF: 5
- realized win: **46.67%**
- MFE >=1%: **40%**
- historical PnL: **+$11.93**
- median MFE: **0.876%**

This is much better than the original 102-trade fresh-supply cohort.

However, it is **not production-ready**.

Chronological weakness:

- TRAIN: 11 trades, 54.5% win
- VALIDATION: **0 trades**
- RESERVE: 4 trades, 25% win

The sample is too small to claim a robust "high probability win area."

More importantly, prior confirmation research already showed:

> confirmation + immediate entry can chase the move and destroy entry economics.

Therefore:

> `ABOVE upper` should be treated as **state validation**, not an immediate buy trigger.

## What can now be avoided?

### At entry

Fresh 15m supply remains:

> **WAIT / REQUIRE PROOF**

It is not yet justified as an unconditional hard block because 19 genuine winners exist.

### After 2 minutes

If the trade / candidate is:

> fresh 15m supply at entry **AND T+2 BELOW lower boundary**

then LQ-3A supports:

> **EARLY REJECTION / ABORT CANDIDATE**

This is not yet an economic exit rule until a causal close/replay is run.

### After 3 minutes

If:

> fresh 15m supply at entry **AND T+3 BELOW lower boundary**

then the state is a very strong:

> **REJECTED LONG THESIS**

Only 1 / 45 historical trades was a genuine winner.

## Is there already a high-win focus area?

Not yet at production confidence.

The best positive structural state is:

> fresh 15m supply -> price above upper boundary by T+3

but its Reserve sample is only 4 trades and does not transport strongly enough.

So LQ-3A does **not** claim:

> this area is guaranteed/high-probability win.

It does show where the next positive research should focus.

## LQ-3A verdict

The useful representation is no longer simply SUPPLY / DEMAND.

For LONG inside fresh 15m supply:

```
ENTRY INSIDE FRESH 15m SUPPLY
          |
          +-- T+2/T+3 BELOW lower
          |      -> REJECTED
          |      -> avoid / abort research candidate
          |
          +-- still INSIDE
          |      -> UNRESOLVED
          |      -> do not promote
          |
          +-- ABOVE upper
                 -> ACCEPTANCE CANDIDATE
                 -> do not chase
                 -> test retest / hold
```

## Next stage

**LQ-3B — Breakout Acceptance + Retest Gate**

Test a causal sequence:

1. LONG candidate starts inside fresh 15m supply.
2. Require actual acceptance above the upper boundary.
3. Do **not** enter immediately on breakout.
4. Wait for pullback / retest toward the broken supply.
5. Require the retest to hold.
6. Enter only after causal reclaim / continuation.
7. Compare TRAIN / VALIDATION / RESERVE economics.

This directly addresses the two facts now established:

- rejection below fresh supply is strongly adverse;
- immediate confirmation entry can chase the move.

No production order authority is changed by LQ-3A.