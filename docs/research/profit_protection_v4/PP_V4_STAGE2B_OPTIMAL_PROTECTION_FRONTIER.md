# PP V4-2B — Optimal Protection Frontier

Status: **COMPLETE — RESEARCH ONLY**

## Executive result

A causal static protection frontier exists.

The preregistered sweep tested **144 rules** on the frozen 99-trade Stage2A cohort using only archived ~5s information available at each observation.

Development:
- EARLY+MID: **66 trades**

Untouched holdout:
- LATE: **33 trades**

Results:
- Pareto frontier: **18 candidates**
- holdout-positive: **6 candidates**

The strongest holdout-positive research reference is:

> **Arm at observed running gross peak +1.50%**  
> **Trigger when current PnL <=90% of running peak**  
> **Require 2 consecutive ~5s observations**

This is shorthand:

`arm=1.50%, retain=90%, confirm=2`

It is a research reference only. It is **not deployed**.

## Best reference — LATE holdout

Historical LATE baseline:
- total realized: **+$0.47**
- win rate: **30.30%**
- observable-net-peak >=0.50% median retention: **31.46%**
- runner >=1% median retention: **36.97%**
- runner >=2% median retention: **43.13%**

Candidate `1.50 / 0.90 / 2`:
- total realized: **+$38.56**
- delta vs baseline: **+$38.10**
- win rate: **33.33%**
- trigger count: **8 / 33**
- median trigger delay from latest running peak: **22.46s**

Observable-net-peak >=0.50%, N=13:
- median retention: **31.46% -> 60.93%**
- >=80% retention share: **0% -> 38.46%**
- nonpositive outcomes: **4 -> 3**
- total realized: **$25.40 -> $63.50**

Runner >=1%, N=8:
- median retention: **36.97% -> 86.42%**
- >=80% retention share: **0% -> 62.50%**
- nonpositive outcomes: **1 -> 0**
- total realized: **$27.18 -> $65.28**

Runner >=2%, N=5:
- median retention: **43.13% -> 73.44%**
- >=80% retention share: **0% -> 40.00%**
- nonpositive outcomes: **1 -> 0**
- total realized: **$20.17 -> $46.27**

All four preregistered LATE guardrails PASS.

## Best reference — full 99-trade diagnostic

Historical:
- total realized: **-$10.02**
- win rate: **36.36%**

Candidate:
- total realized: **+$75.96**
- delta: **+$85.98**
- win rate: **37.37%**
- trigger count: **19 / 99**
- median trigger delay: **24.94s**

Observable-net-peak >=0.50%, N=42:
- median retention: **29.29% -> 47.59%**
- >=80% retention share: **2.38% -> 23.81%**
- nonpositive outcomes: **10 -> 9**
- total realized: **$81.71 -> $167.69**

Runner >=1%, N=20:
- median retention: **36.37% -> 77.27%**
- >=80% retention share: **5% -> 45%**
- total realized: **$71.35 -> $156.03**

Runner >=2%, N=9:
- median retention: **37.17% -> 82.46%**
- >=80% retention share: **0% -> 55.56%**
- nonpositive outcomes: **1 -> 0**
- total realized: **$44.81 -> $104.55**

This candidate is therefore extremely strong for **already-established runners**.

## Chronological concentration diagnostic

Best reference improvement by third:

- EARLY: **+$11.34**, 4 triggers, 4 improved / 0 harmed
- MID: **+$36.54**, 7 triggers, 5 improved / 1 harmed / 1 effectively unchanged
- LATE: **+$38.10**, 8 triggers, 7 improved / 1 harmed

LATE contribution concentration:
- largest contributor share: **40.77%**
- top 3 contributor share: **68.93%**

The holdout gain is not produced by only one trade.

### LATE triggered examples

**USUSDT SHORT**
- actual: **-0.296%**
- simulated: **+2.810%**
- improvement: **+$15.53**

**ATUSDT SHORT**
- actual: **+0.917%**
- simulated: **+2.171%**
- improvement: **+$6.27**

**MORPHOUSDT LONG**
- actual: **+0.889%**
- simulated: **+1.780%**
- improvement: **+$4.46**

**FLOWUSDT LONG**
- actual: **+1.361%**
- simulated: **+1.135%**
- deterioration: **-$1.13**

FLOW is direct evidence that one static rule can still cut a runner too early.

## The frontier reveals two distinct regimes

The strongest high-arm reference protects established runners exceptionally well, but it only triggers **19/99** trades.

As a result:
- full-cohort win rate barely changes: **36.36% -> 37.37%**
- small observed profits remain largely unprotected.

A lower-arm holdout-positive example:

`arm=0.50%, retain=60%, confirm=2`

Full 99 trades:
- total: **+$28.22**
- win rate: **56.57%**
- trigger count: **62 / 99**
- observable-net-peak >=0.50% nonpositive outcomes: **10 -> 1**

But its runner performance is much weaker:
- runner >=1% median retention: **46.85%**
- runner >=2% median retention: **46.56%**
- >=80% runner retention: **0%**

Therefore the data does **not** support one universal static trailing rule.

It supports a two-regime architecture:

1. **small / medium observed profit:** earlier, more aggressive protection;
2. **established runner:** looser high-retention runner mode.

That is the exact research question for V4-2C.

## Stage2B decision

Stage2B passes its research objective:

- static causal protection can materially improve realized PnL;
- six candidates survive untouched LATE holdout guardrails;
- the best high-arm reference strongly improves runner retention;
- a low-arm reference improves win conversion but sacrifices runner capture;
- a runner trade-off remains observable.

Proceed to:

> **V4-2C — Runner Preservation / Two-Regime Protection**

Stage2C should test a causal hybrid:
- aggressive protection below runner qualification;
- runner-preservation mode after a sufficiently strong observable peak;
- no future MFE;
- explicit transition rules;
- compare against both the historical baseline and the best Stage2B static references.

## Runtime decision

- no Stage2B policy deployed;
- no runtime change;
- no new REDUCE/CLOSE authority;
- observer remains research-only;
- live remains disabled/disarmed.

## Frozen artifacts

- preregistration:
  `docs/research/profit_protection_v4/PP_V4_STAGE2B_OPTIMAL_PROTECTION_FRONTIER_CONTRACT.md`
- evaluator:
  `research/profit_protection_v4/stage2b_optimal_protection_frontier.py`
- complete 144-candidate sweep:
  `research/profit_protection_v4/results/stage2b_optimal_protection_frontier_sweep.json`
- frozen result:
  `research/profit_protection_v4/results/stage2b_optimal_protection_frontier.json`
