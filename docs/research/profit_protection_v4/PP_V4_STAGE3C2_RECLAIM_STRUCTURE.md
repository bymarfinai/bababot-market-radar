# PP V4-3C2 — Reclaim Structure / False-Reversal Discriminator

Status: **COMPLETE — NO PASS**

Baseline:

> **Profit Protector V4.2 — Hybrid Protection**

Stage3C2 tested whether the structure of the rebound after an initial runner giveback could reduce false-reversal exits without sacrificing the strong retention V4.2 already achieves when its runner close is correct.

## Population

Same historical runner-capable population as Stage3C:

- observed peak >= +1.50%: **19 trades**
- DEV: **12**
- LATE chronology check: **7**

## Frozen candidate family

Exactly **81 candidates**:

- initial giveback floor: 90%, 85%, 80%
- reclaim probe window: 5s, 10s, 15s
- reclaim fraction threshold: 25%, 50%, 75%
- rebound velocity threshold: 0.00, 0.01, 0.02 pp/s

No values were added after results were inspected.

## DEV gates

A candidate had to satisfy all five:

1. coverage >=50%
2. precision >=65%
3. premature share <=35%
4. median correct retention >=80%
5. correct signals retaining >=80% >=50%

## Result: 0 / 81 eligible

| Gate | Candidates passing |
|---|---:|
| Coverage | **81 / 81** |
| Precision | **0 / 81** |
| Premature share | **0 / 81** |
| Median retention | **34 / 81** |
| >=80 retention share | **37 / 81** |
| All five | **0 / 81** |

Gate-count distribution:

- 1 gate: 44 candidates
- 2 gates: 3
- 3 gates: 34
- 4 gates: 0
- 5 gates: 0

The dominant failure remains false-reversal discrimination, not signal coverage.

## Highest-precision candidate

Parameters:

- floor: **80%**
- probe window: **15s**
- reclaim fraction threshold: **25%**
- rebound velocity threshold: **0.00 pp/s**

DEV outcome:

- signals: **11 / 12**
- correct: **7**
- premature: **4**
- precision: **63.64%**
- premature share: **36.36%**
- median correct retention: **68.11%**
- correct retention >=80%: **14.29%**

This came close to the precision requirement but only after retention had already fallen far below the 80% objective.

It therefore fails both the precision and retention intent of Stage3C2.

## Best high-retention shape among >=50% precision

A representative high-retention candidate:

- floor: **85%**
- probe window: **5s**
- reclaim fraction threshold: **75%**
- rebound velocity threshold: **0.00 pp/s**

DEV:

- signals: **12 / 12**
- correct: **6**
- premature: **6**
- precision: **50%**
- median correct retention: **83.58%**
- correct retention >=80%: **83.33%**

This preserves profit well but does not improve false-reversal precision.

It reproduces the same trade-off seen in V4.2:

> act early enough to protect profit and false reversals remain high; wait for stronger evidence and retention deteriorates.

## Persistent false-reversal examples

With the high-retention 85% / 5s / 75% reclaim candidate, premature signals still occurred on examples including:

- AVAAI
- STX
- COMP
- API3
- AVA
- FLOW

The most selective 80% / 15s / 25% reclaim candidate still falsely signalled:

- AVAAI
- STX
- COMP
- FLOW

This is important because those same names repeatedly appear as continuation-after-giveback problems across Stage3B/3C/3C2.

A single bounded reclaim probe does not contain enough information to distinguish them robustly.

## Baseline comparison

### V4.2 runner baseline — all 19

- precision: **52.63%**
- correct final-reversal closes: **10**
- premature closes: **9**
- median correct retention: **85.60%**
- correct signals >=80% retention: **80%**

### Stage3C closest near-miss — DEV

80% floor / 60s age / 0.03 pp/s velocity / 5s wait:

- precision: **60%**
- premature: **40%**
- median correct retention: **62.98%**

### Stage3C2 highest-precision candidate — DEV

80% floor / 15s probe / 25% reclaim:

- precision: **63.64%**
- premature: **36.36%**
- median correct retention: **68.11%**

Stage3C2 improves the precision/retention frontier somewhat versus the Stage3C near-miss, but still does not cross the preregistered target.

## Interpretation

Stage3C2 rejects a second simple hypothesis:

> one bounded reclaim probe, even with reclaim magnitude and rebound velocity, is not sufficient to identify final reversal early enough.

What is missing is likely **structure across multiple failed/recovered attempts**, or normalization for the trade's own local volatility.

The persistent false-reversal cases often survive one shallow/deep pullback and then resume much later. A one-probe detector cannot infer that continuation reliably from only a short rebound window.

## Next research direction

Do not proceed to Stage3D with Stage3C2.

The next preregistered research stage should test a compact richer family such as:

1. **multi-cycle failed reclaim count**
   - distinguish first pullback from repeated inability to regain a prior zone;

2. **volatility-normalized giveback**
   - measure drawdown relative to recent 5s movement/noise rather than only percent of running peak;

3. **reclaim-zone persistence**
   - time spent above/below a recovered fraction of the peak-to-trough range;

4. **selloff curvature / deceleration across multiple observations**
   - not only instantaneous velocity.

This must be a new preregistered stage; these features were not tested in Stage3C2.

## Decision

**Stage3C2 = NO PASS.**

- no candidate selected;
- no Stage3D integration;
- no runtime change;
- no paper/prospective shadow;
- V4.2 remains the frozen baseline.

Full artifacts:
- `research/profit_protection_v4/results/stage3c2_reclaim_structure_sweep.csv`
- `research/profit_protection_v4/results/stage3c2_reclaim_structure_population.csv`
- `research/profit_protection_v4/results/stage3c2_reclaim_structure_summary.json`
