# PP V4-3C — Temporal Reversal Detector

Status: **COMPLETE — NO PASS**

Baseline under study:

> **Profit Protector V4.2 — Hybrid Protection**

Stage3C was run exactly against the preregistered candidate family. No gate or parameter range was relaxed after seeing results.

## Objective

Stage3B showed that a fixed giveback threshold is insufficient because many apparent reversals are temporary pullbacks followed by a new high.

Stage3C therefore tested whether a causal combination of:

- giveback floor,
- time since last running high,
- latest downward PnL velocity,
- and short reclaim-confirmation wait

could distinguish a true final reversal from a transient pullback while still preserving at least 75% of the final observed runner peak.

## Population

Runner-capable historical trades:

- **19** trades with archived observed peak >= +1.50%
- chronological DEV: **12**
- chronological LATE: **7**

Stage3B had already inspected the overall history, so LATE is a chronology robustness slice, not claimed as a pristine untouched holdout.

## Frozen candidate space

Exactly **144 candidates**:

- floor: 90%, 85%, 80%
- minimum peak age: 10s, 20s, 30s, 60s
- minimum downward velocity: 0.00, 0.02, 0.03, 0.04 pp/s
- reclaim wait: 0s, 5s, 10s

No other values were added.

## DEV gates

A candidate had to satisfy all four:

1. signal coverage >=50%
2. correct-final-reversal precision >=60%
3. premature false-reversal share <=40%
4. median correct-signal retention >=75% of final archived observed peak

## Result: 0 / 144 eligible

| Gate | Candidates passing |
|---|---:|
| Coverage | **144 / 144** |
| Precision | **2 / 144** |
| Premature-share | **2 / 144** |
| Retention | **74 / 144** |
| All four | **0 / 144** |

Gate-count distribution:

- 1 gate: 68 candidates
- 2 gates: 74
- 3 gates: 2
- 4 gates: **0**

Therefore Stage3C has **NO PASS** under the preregistered requirements.

## Two closest candidates

Both near-misses used:

- floor = **80%**
- minimum age = **60s**
- minimum velocity = **0.03 pp/s**

### Wait 5s

- coverage: **83.33%**
- correct final reversal: **6**
- premature: **4**
- precision: **60%**
- premature share: **40%**
- median correct retention: **62.98%**
- correct signals retaining >=80%: **0%**

### Wait 10s

- coverage: **83.33%**
- correct final reversal: **6**
- premature: **4**
- precision: **60%**
- premature share: **40%**
- median correct retention: **54.14%**
- correct signals retaining >=80%: **0%**

These candidates solve the precision gate only by waiting so long/deep that the profit-protection objective is lost.

That is not acceptable.

## V4.2 runner temporal baseline

Across all 19 runner-capable trades, V4.2 itself produced:

- signals: **19 / 19**
- correct post-final-peak closes: **10**
- premature false-reversal closes: **9**
- precision: **52.63%**
- median retention among correct closes: **85.60%**
- correct closes >=80% of final observed peak: **80%**
- correct closes >=75%: **90%**

This reveals the core trade-off:

> V4.2 already preserves the runner very well **when its reversal call is correct**, but it calls reversal too early on too many continuations.

The Stage3C simple temporal filters can improve precision to 60%, but only by waiting until median retention falls far below the protection target.

## DEV vs LATE baseline asymmetry

V4.2 temporal behavior was materially different by chronology.

DEV:
- 5 correct / 7 premature
- precision: **41.67%**
- median correct retention: **82.93%**

LATE:
- 5 correct / 2 premature
- precision: **71.43%**
- median correct retention: **88.02%**

Naive fixed floors also looked much better in LATE than DEV.

This chronology asymmetry is another reason not to force a fitted winner out of the current 19-trade runner sample.

## Naive floor baselines

### 90% floor

DEV:
- precision **25%**
- 9 premature / 3 correct
- median correct retention **78.44%**

LATE:
- precision **71.43%**
- 2 premature / 5 correct
- median correct retention **88.80%**

### 85% floor

DEV:
- precision **41.67%**
- 7 premature / 5 correct
- median correct retention **78.44%**

LATE:
- precision **71.43%**
- 2 premature / 5 correct
- median correct retention **78.88%**

### 80% floor

DEV:
- precision **50%**
- 6 premature / 6 correct
- median correct retention **73.61%**

LATE:
- precision **71.43%**
- 2 premature / 5 correct
- median correct retention **78.88%**

A fixed floor therefore remains rejected.

## Interpretation

Stage3C answers an important engineering question:

> **Age + instantaneous downward velocity + a short wait are not sufficient to solve transient-vs-final reversal at the required retention target.**

The failure mechanism is not lack of a threshold. The detector needs information that identifies **reclaim structure before requiring a deep giveback**.

The next causal feature family should be preregistered separately rather than sneaked into this stage after seeing failure.

High-value candidates for a new research stage include:

- partial reclaim strength after an initial giveback, not merely a new all-time running high;
- multi-sample curvature / deceleration of the selloff;
- peak formation structure immediately before giveback;
- local volatility-normalized giveback rather than only percentage-of-peak;
- repeated failed-reclaim structure.

These are recommendations for the next preregistered stage only; they were not tested in Stage3C.

## Decision

**Do not proceed to V4-3D with the current Stage3C detector.**

Stage3C status:

> **NO PASS — temporal detector family insufficient**

Required next step:

> a new preregistered causal-feature expansion focused on **reclaim structure / false-reversal discrimination**.

Restrictions remain:
- no runtime change;
- no paper/prospective shadow;
- V4.2 baseline unchanged;
- true/final peak remains evaluation-only;
- no claim of final-peak prediction.
