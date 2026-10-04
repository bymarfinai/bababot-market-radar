# PP V4-3C2 — Reclaim Structure / False-Reversal Discriminator Contract

Status: **PREREGISTERED BEFORE CANDIDATE OUTCOME INSPECTION**

Baseline: **Profit Protector V4.2 — Hybrid Protection**

## Objective

Stage3C showed that simple floor + age + instantaneous velocity + wait cannot improve false-reversal precision without sacrificing too much runner retention.

Stage3C2 tests a richer but still causal hypothesis:

> after an initial runner giveback, the *shape of the attempted reclaim* contains information that separates transient pullbacks from genuine reversals earlier than a long fixed wait.

Stage3C2 remains a detector study only. It does not change runtime authority, position sizing, or small-profit protection architecture.

## Population

Primary:
- the same 19 historical runner-capable V4.2-triggered trades used in Stage3C;
- archived observed peak >= +1.50%.

Chronology:
- DEV = first 12 trades by opened_at_ms;
- LATE = final 7 trades, used only as chronology robustness check.
- LATE is not claimed as pristine because Stage3B/3C already inspected overall history.

## Causal state machine

A candidate starts a **reclaim probe** only after:
- running observed peak >= +1.50%; and
- current PnL first crosses below a chosen giveback floor.

At probe start record:
- running peak P;
- initial crossing PnL C;
- initial drawdown depth D = P - C.

During a bounded probe window, using observations available so far only:
- trough T = lowest PnL seen since probe start;
- best rebound B = highest PnL observed after T;
- reclaim fraction R = (B - T) / max(P - T, epsilon);
- rebound velocity = positive PnL change per second from T to B;
- post-trough direction over the last sample.

At the end of the probe window:
- if a new running high was made, cancel the probe;
- otherwise emit REVERSAL only when the reclaim structure fails the candidate reclaim requirements.

No future peak or true MFE is available to the signal.

## Frozen candidate family

Initial giveback floor:
- **90%, 85%, 80%** of current running peak.

Probe window:
- **5s, 10s, 15s**.

Minimum reclaim fraction required to cancel reversal:
- **25%, 50%, 75%** of peak-to-trough drawdown.

Minimum rebound velocity required to cancel reversal:
- **0.00, 0.01, 0.02 percentage-points/sec**.

Signal semantics:
- at probe-window expiry, cancel if either:
  1. a new running high occurred; or
  2. reclaim fraction >= threshold **and** rebound velocity >= threshold.
- otherwise emit REVERSAL at the first observation at/after probe expiry.

Candidate count = 3 × 3 × 3 × 3 = **81**.

No parameter values may be added after results are inspected.

## Evaluation labels

Research-only, post hoc labels:

- **PREMATURE_FALSE_REVERSAL**:
  after the detector signal, a later archived observation exceeds the running peak that existed when the reclaim probe began.

- **CORRECT_FINAL_REVERSAL**:
  no later archived observation exceeds that probe-start running peak.

The future label is not a runtime input.

## Retention scoring

For CORRECT_FINAL_REVERSAL signals:
- retention = signal PnL / final archived observed peak;
- report median;
- report share >=80%;
- report share >=75%.

For PREMATURE signals:
- report future higher peak;
- report signal-to-future-high seconds.

## DEV gates

A candidate is DEV-eligible only if all hold:

1. signal coverage >= **50%** of DEV runner trades;
2. correct-final-reversal precision >= **65%**;
3. premature share <= **35%**;
4. median correct retention >= **80%** of final observed peak;
5. correct signals retaining >=80% >= **50%**.

These gates are intentionally stricter than Stage3C because the purpose of Stage3C2 is specifically to improve false-reversal discrimination **without giving up V4.2's retention strength**.

## DEV ranking

Among eligible candidates rank lexicographically by:

1. highest precision;
2. lowest premature share;
3. highest >=80 retention share;
4. highest median correct retention;
5. highest signal coverage;
6. shorter probe window;
7. higher initial floor;
8. lower reclaim threshold;
9. lower rebound-velocity threshold.

## LATE validation

Freeze the top DEV candidate and replay unchanged on LATE.

Report:
- coverage;
- correct / premature counts;
- precision;
- median correct retention;
- >=80 retention share;
- per-trade outcomes.

No post-LATE retuning.

## Baselines

Compare against:
- V4.2 runner close temporal behavior;
- Stage3C closest near-miss;
- naive fixed 90/85/80 floor.

## Decision

If no candidate passes all DEV gates:
- Stage3C2 = **NO PASS**;
- do not relax gates post hoc;
- do not advance to Stage3D with Stage3C2.

If at least one candidate passes:
- nominate one frozen candidate for Stage3D integration research only.

Restrictions:
- historical real data only;
- no paper/prospective shadow;
- no runtime change;
- no future true/final peak in causal features;
- no claim of final-peak prediction.
