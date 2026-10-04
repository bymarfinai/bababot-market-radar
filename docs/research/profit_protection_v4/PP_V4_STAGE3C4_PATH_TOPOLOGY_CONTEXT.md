# PP V4-3C4 — Path Topology & Market-State Context

Status: **COMPLETE — NO PASS**

Baseline:

> **Profit Protector V4.2 — Hybrid Protection**

## Why Stage3C4 changed the framing

Stages 3C, 3C2, and 3C3 all tried to replace or delay the runner close with another reversal detector.

Stage3C4 instead kept the existing V4.2 runner close as the base trigger and tested a narrower intervention:

> **veto a V4.2 close only when recent path topology still looks continuation-supportive.**

This targets the actual V4.2 weakness directly:
- V4.2 retention is already strong when the reversal call is correct;
- the problem is premature close on a continuation.

## Context data audit

The old WD5H feature CSV could **not** be joined to these 19 runner trades by exact position_id because it belongs to an earlier historical cohort.

Stage3C4 therefore rejected symbol/time proxy matching.

Instead, exact causal context was recovered for **19 / 19** runner trades from:

- exact `signal_id` stored in `trade_events`;
- the corresponding `signals` row;
- Stage11C evidence families stored in `positions.raw_json`.

Thus entry context is genuine trade-specific context, not a proxy cohort join.

Strong entry context was present on **11 / 19** trades.

Definition:
- at least 3 of 4 Stage11C evidence families ALIGNED/SUPPORTIVE;
- decision_context_balance >=3.

This context is static entry-time context only. No claim is made that it represents market state at the later protection timestamp.

## Frozen candidate family

Exactly **12 candidates**:

- topology lookback: 30s or 60s;
- required continuation votes: 2, 3, or 4;
- context mode:
  - PATH_ONLY
  - CONTEXT_BONUS

Path votes:

1. recent half forms a higher minimum than older half;
2. recovery slope over lookback is positive;
3. recent 5s volatility contracts to <=80% of older-half volatility;
4. <=50% of lookback samples are underwater below the 90% running-peak floor.

CONTEXT_BONUS adds one vote for strong entry context.

Veto:
- fixed 10s grace;
- a new running high makes the veto successful;
- otherwise close at grace expiry;
- maximum 2 vetoes.

No values were added after results were inspected.

## DEV result

Runner DEV population: **12**.

V4.2 DEV baseline:
- signals: 12
- correct final reversal: **5**
- premature: **7**
- precision: **41.67%**
- median correct retention: **82.93%**
- correct retention >=80%: **60%**

Stage3C4 sweep:

| Gate | Candidates passing |
|---|---:|
| Coverage >=50% | **12 / 12** |
| Precision >=65% | **0 / 12** |
| Premature <=35% | **0 / 12** |
| Median correct retention >=80% | **10 / 12** |
| >=80 retention share >=50% | **10 / 12** |
| Premature count lower than V4.2 | **4 / 12** |
| All gates | **0 / 12** |

Stage3C4 therefore has **NO PASS**.

## Best observed DEV candidate

The best precision candidate was:

> **60s lookback / 3 votes / PATH_ONLY**

Results:

- signals: **12 / 12**
- correct: **6**
- premature: **6**
- precision: **50%**
- premature share: **50%**
- median correct retention: **83.31%**
- correct retention >=80%: **66.67%**
- vetoes started: **2**
- successful vetoes: **1**
- grace-timeout closes: **1**

Compared with V4.2 DEV:

- correct: 5 -> **6**
- premature: 7 -> **6**
- precision: 41.67% -> **50%**
- median retention: 82.93% -> **83.31%**

So topology produces a real but small improvement without damaging retention.

It is still far below the preregistered 65% precision requirement.

## What the best veto actually changed

### MANTRA — successful rescue

V4.2:
- premature runner close.

Stage3C4:
- recent 60s path fired 3 continuation votes:
  - higher low;
  - positive recovery slope;
  - volatility contraction.
- close was vetoed;
- a new running high occurred about 10 seconds later;
- eventual signal became a correct final-reversal close;
- retention remained about **85.9%** of final observed peak.

This is the clearest positive case for the topology hypothesis.

### AVAAI — false veto

At the V4.2 close candidate:
- higher-low = true;
- positive recovery slope = true;
- volatility contraction = true;
- 3 votes triggered a veto.

But:
- no new high arrived inside the fixed 10s grace;
- close happened at grace timeout;
- the path much later resumed and made a substantially higher peak.

The topology correctly recognized that the path was not simply collapsing, but the short causal window still could not know that continuation would resume much later.

This is the same fundamental difficulty exposed by earlier stages.

## Entry context did not help

The corresponding:

> **60s / 3 votes / CONTEXT_BONUS**

performed worse:

- signals: **11**
- correct: **5**
- premature: **6**
- precision: **45.45%**
- median correct retention: **82.93%**
- vetoes started: **6**
- successful vetoes: **1**
- grace-timeout closes: **5**

The static entry-context bonus caused more vetoes but almost all additional vetoes timed out.

Examples include delaying closes on BR, API3, AVA, and FLOW without producing enough additional continuation discrimination.

Conclusion:

> a strong entry thesis is not sufficient evidence that a later runner pullback is transient.

That context may be useful for entry quality, but it should not be treated as a standalone runner-continuation prior this late in the trade.

## Comparison with previous stages

DEV frontier:

- V4.2: precision **41.67%**, median correct retention **82.93%**
- Stage3C closest near-miss: precision **60%**, retention **62.98%**
- Stage3C2 highest precision: **63.64%**, retention **68.11%**
- Stage3C3 highest precision: **50%**, retention **80.99%**
- Stage3C4 best: **50%**, retention **83.31%**

Stage3C4 is the first post-3C experiment to improve premature count while preserving or slightly improving the V4.2 retention profile.

But the gain is only one DEV trade and is not sufficient for promotion.

## Interpretation

Stage3C4 adds an important refinement:

> **path topology contains some continuation information, but the simple four-vote topology and static entry context are not enough to make final-reversal classification reliable.**

The remaining hard cases can:
- form apparent higher lows;
- show positive short recovery slopes;
- contract short-term volatility;
- and still fail to make a new high for longer than 10 seconds before eventually continuing.

This means the missing discriminator likely requires one of:

1. a genuinely dynamic market-state snapshot at the protection timestamp;
2. richer topology across a longer structural horizon;
3. cross-market / order-flow state contemporaneous with the pullback;
4. more runner examples before fitting additional structure.

Importantly, entry-time context should not be substituted for contemporaneous protection-time context.

## Decision

**Stage3C4 = NO PASS.**

- no candidate selected;
- no LATE candidate tuning;
- do not proceed to Stage3D;
- do not relax gates post hoc;
- V4.2 remains the frozen baseline;
- no runtime change;
- no paper/prospective shadow.

Artifacts:
- `research/profit_protection_v4/results/stage3c4_path_topology_context_sweep.csv`
- `research/profit_protection_v4/results/stage3c4_path_topology_context_population.csv`
- `research/profit_protection_v4/results/stage3c4_path_topology_context_entry_context.csv`
- `research/profit_protection_v4/results/stage3c4_path_topology_context_summary.json`
