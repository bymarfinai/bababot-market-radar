# LP-2B — Sub-0.5 Stall / BE Protector Discovery

Status: **MIXED RESULT**
- **Direct BE arming while green: FAIL**
- **Sub-0.5 stall-cut after decay: PASS as research candidate**
- Nothing is production-ready.

## Objective

LP-2B tests the user's intended idea:

> protect trades that are genuinely headed toward a sub-0.5% outcome, without arming BE on future runners that merely pass through +0.18% to +0.50%.

The full resolved LONG universe remains 1,236.

Target bad class:
- historical max MFE < +0.50%
- historical realized PnL <= 0
- N = **626**

Control:
- future historical max MFE >= +0.50%
- N = **608**

The two rare realized-positive trades whose max MFE stayed below +0.50% are excluded from the binary discovery duel.

## Lane A — True BE arming while still green

To be a real +0.18% BE protector, the rule must be armed while:
- running MFE >= +0.18%
- running MFE < +0.50%
- current side return >= +0.18%

Otherwise +0.18% can no longer be guaranteed.

### Base-rate problem

Eligible state counts:

| Snapshot | Split | Eligible | Eventual sub-0.5 failure | Future >=0.5 |
|---|---|---:|---:|---:|
| T+2 | D | 80 | 16 | 64 |
| T+2 | V | 40 | 13 | 27 |
| T+2 | R | 30 | 6 | 24 |
| T+3 | D | 77 | 24 | 53 |
| T+3 | V | 27 | 10 | 17 |
| T+3 | R | 28 | 4 | 24 |

Especially on Reserve at T+3:
- only **4 / 28** are eventual sub-0.5 failures
- **24 / 28** later reach >= +0.50%

So “still green in the +0.18% to +0.50% zone” is more often a future runner than a stall.

### Exhaustive candidate search

LP-2B searched T+2 and T+3:
- top causal temporal features
- 2-feature and 3-feature deterministic conjunctions
- Development threshold search
- Validation screening
- Reserve opened last

Practical BE gate:
- precision >= 70% in D/V/R
- bad recall >= 10% in D/V/R
- at least 5 Reserve fires

Result:

> **ZERO candidates passed.**

Even a relaxed gate:
- precision >= 60% in D/V/R
- bad recall >= 10% in D/V/R
- at least 5 Reserve fires

also produced:

> **ZERO candidates.**

### Lane A conclusion

**FAIL.**

There is currently no stable causal rule that can identify enough eventual sub-0.5 failures **while they are still safely above +0.18%**.

Therefore the original idea:

> “arm +0.18% BE only for trades that will remain below +0.50%”

is not currently implementable with acceptable reliability from the frozen T+2/T+3 information.

This is an important negative result and must not be hidden.

---

## Lane B — Sub-0.5 stall-cut after decay

LP-2B then tested a different question:

> once the trade has failed to build excursion and has already begun to deteriorate, can a high-precision stall state be identified?

This is no longer a BE rule. It is an early stall/loss-cut candidate.

### Selected research candidate

Decision point:
- **T+3**
- median ~**2.61 minutes after entry**

All conditions:

1. running MFE <= **+0.140056%**
2. current side return <= **-0.189349%**
3. selected-side VWAP extension 20 <= **+0.516788**

Interpretation:

> by T+3 the LONG has built almost no favorable excursion, is already around -0.19% or worse, and has no strong selected-side VWAP extension supporting recovery.

### D / V / R

| Metric | Development | Validation | Reserve |
|---|---:|---:|---:|
| Precision | **82.65%** | **96.55%** | **88.24%** |
| Sub-0.5 failure recall | **22.69%** | **20.90%** | **22.22%** |
| Future >=0.5 harmed | **4.43%** | **0.88%** | **3.60%** |
| Recovered-winner harm | **2.76%** | **2.56%** | **6.82%** |
| Normalized net delta | **+$37.63** | **+$22.87** | **+$9.71** |

Reserve remains positive and winner harm remains below 7%.

### Full-universe descriptive application

- fires: **161**
- sub-0.5 failures caught: **139 / 626 = 22.20%**
- future >=0.5 harmed: **22 / 608 = 3.62%**
- recovered winners harmed: **8 / 228 = 3.51%**
- all realized-positive trades harmed: **9 / 304 = 2.96%**
- precision: **86.34%**

Normalized T+3 economic comparison:

- historical PnL on fired trades: **-$418.39**
- normalized T+3 close: **-$348.18**
- estimated improvement: **+$70.21**

Split normalized delta:
- Development: +$37.63
- Validation: +$22.87
- Reserve: +$9.71

Again, this is **not exact execution PnL**.

### Path-level descriptive effect

| Path | Fired N | Historical PnL | Normalized T+3 close | Delta |
|---|---:|---:|---:|---:|
| WRONG_DIRECTION | 134 | -$411.92 | -$293.80 | **+$118.12** |
| STALL | 5 | -$20.90 | -$12.80 | **+$8.10** |
| MISSED_OPPORTUNITY | 13 | -$13.43 | -$27.86 | **-$14.43** |
| RECOVERED_WINNER | 8 | +$25.18 | -$12.45 | **-$37.63** |
| CLEAN_WINNER | 1 | +$2.69 | -$1.27 | **-$3.96** |
| **TOTAL** | **161** | **-$418.39** | **-$348.18** | **+$70.21** |

## LP-2B conclusion

1. **Direct +0.18% BE arming is NOT supported.**
2. The reason is structural: while trades are still green between +0.18% and +0.50%, future runners substantially outnumber eventual stalls.
3. A valid stall signal becomes more identifiable only after meaningful decay has already happened.
4. The selected T+3 stall-cut candidate is stable enough for further research, but it is **not BE** and must never be labeled as one.
5. LP-2B therefore changes the architecture:

Instead of:

> touch +0.18% -> classify -> BE

the evidence currently supports:

> watch sub-0.5 progression -> if high-confidence decay appears -> small-loss cut

6. True break-even protection may require richer intra-window path information or later adaptive state tracking than the frozen T+2/T+3 snapshots provide.

## Recommended next step

Before combining LP-2A and LP-2B:

**LP-3 — Winner Harm & Protector Interaction Test**
- apply LP-2A wrong-direction candidate and LP-2B stall-cut candidate together
- define precedence if both fire
- measure overlap
- quantify unique loss dollars saved
- quantify recovered/clean winner harm
- then perform execution-realistic replay on the current operational cohort.

No deployment is authorized by LP-2B.
