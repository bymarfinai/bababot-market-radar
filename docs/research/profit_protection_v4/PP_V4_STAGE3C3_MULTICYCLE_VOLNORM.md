# PP V4-3C3 — Multi-Cycle Reclaim & Volatility-Normalized Reversal

Status: **COMPLETE — NO PASS**

Baseline:

> **Profit Protector V4.2 — Hybrid Protection**

Stage3C3 tested whether repeated failed reclaim cycles plus a local-volatility-normalized giveback could distinguish continuation from final reversal earlier than the Stage3C/3C2 families.

## Population

Same historical runner-capable population:

- observed peak >= +1.50%: **19 trades**
- DEV: **12**
- LATE chronology check: **7**

## Frozen candidate family

Exactly **32 candidates**:

- initial floor: 90%, 85%
- local-noise lookback: 6 or 12 samples
- reclaim fraction: 25%, 50%
- required failed reclaim cycles: 1 or 2
- minimum normalized drawdown: 2.0 or 3.0 local-noise units

No values were added after outcome inspection.

## DEV gates

A candidate had to satisfy all five:

1. coverage >=50%
2. precision >=65%
3. premature share <=35%
4. median correct retention >=80%
5. correct signals retaining >=80% >=50%

## Result: 0 / 32 eligible

| Gate | Candidates passing |
|---|---:|
| Coverage | **32 / 32** |
| Precision | **0 / 32** |
| Premature share | **0 / 32** |
| Median retention | **22 / 32** |
| >=80 retention share | **25 / 32** |
| All five | **0 / 32** |

Gate-count distribution:

- 1 gate: 7 candidates
- 2 gates: 3
- 3 gates: 22
- 4 gates: 0
- 5 gates: 0

Again, the limiting factor is false-reversal discrimination rather than retention or signal availability.

## Highest-precision candidate

Parameters:

- initial floor: **90%**
- local-noise lookback: **12 samples**
- reclaim fraction: **25%**
- failed reclaim cycles: **1**
- minimum drawdown: **3.0 noise units**

DEV:

- signals: **10 / 12**
- correct: **5**
- premature: **5**
- precision: **50%**
- premature share: **50%**
- median correct retention: **80.99%**
- correct signals retaining >=80%: **60%**
- correct signals retaining >=75%: **80%**

This is the important contrast with Stage3C2:

> retention now crosses the desired 80% median, but precision collapses back to 50%.

So volatility normalization can preserve timing, but does not tell us whether the giveback is terminal.

## Representative high-retention candidate

Parameters:

- floor: 90%
- noise lookback: 12
- reclaim fraction: 25%
- failed cycles: 1
- drawdown >=2.0 noise units

DEV:

- signals: **10 / 12**
- correct: **4**
- premature: **6**
- precision: **40%**
- median correct retention: **84.09%**
- >=80 retention share: **75%**
- >=75 retention share: **100%**

This protects profit well when correct, but has even worse false-reversal precision.

## Two failed-reclaim cycles did not solve the problem

Best DEV precision among candidates requiring **2 failed cycles**:

- precision: **44.44%**
- median correct retention: **72.32%**

Representative parameters:
- floor 90%
- 12-sample noise
- reclaim 25%
- 2 failed cycles
- 3.0 noise units

So requiring another failed reclaim:

1. did **not** increase precision above the one-cycle best;
2. delayed the signal enough to reduce retention.

That directly rejects the idea that simply waiting for a second failed reclaim is sufficient.

## Persistent premature examples

The highest-precision Stage3C3 candidate still produced premature reversal signals on:

- **AVAAI**
- **STX**
- **COMP**
- **API3**
- **FLOW**

Examples of normalized giveback at the premature signal:

- AVAAI: about **4.0 noise units**
- STX: about **11.5 noise units**
- COMP: about **5.0 noise units**
- API3: about **4.0 noise units**
- FLOW: about **5.0 noise units**

This is a strong negative result:

> even a giveback that is very large relative to recent local 5s noise can still be a temporary pullback followed by a later higher peak.

Therefore local-volatility normalization alone cannot distinguish terminal reversal from continuation.

## Comparison with earlier stages

### V4.2 runner baseline — all 19

- precision: **52.63%**
- median correct retention: **85.60%**
- correct signals >=80% retention: **80%**

### Stage3C closest near-miss — DEV

- precision: **60%**
- median retention: **62.98%**

### Stage3C2 highest precision — DEV

- precision: **63.64%**
- median retention: **68.11%**

### Stage3C3 highest precision — DEV

- precision: **50%**
- median retention: **80.99%**

The three experiments now expose a stable frontier:

- waiting / deeper confirmation improves precision somewhat but destroys retention;
- early volatility-normalized protection preserves retention but cannot identify continuation reliably.

## Interpretation

Three simple causal families have now been falsified as standalone solutions:

1. **Stage3C:** floor + age + instantaneous velocity + fixed wait;
2. **Stage3C2:** one bounded reclaim probe;
3. **Stage3C3:** multi-cycle failed reclaim + local-volatility normalization.

The remaining error is concentrated in paths that can suffer large, repeated, statistically unusual pullbacks and still resume to a higher peak later.

This suggests the missing information is not another scalar threshold.

A next research stage should focus on **path topology / market-state context**, for example:

- relation between successive local highs and lows;
- time-under-water relative to running peak;
- expansion/contraction of local volatility before and after the pullback;
- whether the recovery is forming higher lows despite failure to make a new high;
- external directional/context features already available to Market Detector, evaluated causally at the protection timestamp.

Those features were not tested here and require a new preregistered stage.

## Decision

**Stage3C3 = NO PASS.**

- no detector candidate selected;
- do not proceed to Stage3D;
- do not relax gates post hoc;
- V4.2 remains the frozen protection baseline;
- no runtime change;
- no paper/prospective shadow.

Artifacts:
- `research/profit_protection_v4/results/stage3c3_multicycle_volnorm_sweep.csv`
- `research/profit_protection_v4/results/stage3c3_multicycle_volnorm_population.csv`
- `research/profit_protection_v4/results/stage3c3_multicycle_volnorm_summary.json`
