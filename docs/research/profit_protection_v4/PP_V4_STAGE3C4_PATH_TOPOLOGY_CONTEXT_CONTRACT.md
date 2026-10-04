# PP V4-3C4 — Path Topology & Market-State Context Contract

Status: **PREREGISTERED BEFORE CANDIDATE OUTCOME INSPECTION**

Baseline: **Profit Protector V4.2 — Hybrid Protection**

## Objective

Stages 3C–3C3 showed a stable failure frontier:
- when V4.2 calls reversal correctly, runner retention is already strong;
- the dominant problem is premature close on continuation paths;
- additional scalar giveback, wait, reclaim, and local-volatility thresholds did not solve that discrimination problem.

Stage3C4 therefore does **not** replace V4.2 with another standalone trailing rule.

It tests a causal **continuation veto layer** on top of the existing V4.2 runner-close candidate.

At the moment V4.2 would close a runner, Stage3C4 asks:

> does the recent path topology plus entry-time market context still look continuation-supportive enough to veto this close briefly?

## Population

Same runner-capable historical population:
- V4.2-triggered trades;
- archived observed peak >= +1.50%;
- 19 trades total;
- first 12 chronological = DEV;
- final 7 = LATE chronology robustness check.

## Causal data

### Dynamic path topology

Computed only from archived 5s observations at or before the candidate-close timestamp.

Allowed path features:

1. **higher-low vote**
   - split the topology lookback into two equal halves;
   - compare the minimum directional PnL in the recent half with the minimum in the older half;
   - vote continuation if recent-half minimum >= older-half minimum.

2. **positive recovery-slope vote**
   - ordinary least-squares slope of directional PnL over the full topology lookback;
   - vote continuation if slope > 0.

3. **volatility-contraction vote**
   - median absolute 5s PnL change in the recent half divided by the older half;
   - vote continuation if ratio <= 0.80.

4. **brief-underwater vote**
   - compute the share of samples in the lookback at or below 90% of the current running peak;
   - vote continuation if share <= 0.50.

### Static entry-time context

These values are allowed only because they were already known before the position opened and can be joined exactly for all 19 runner trades.

Context source:
- exact signal_id from `trade_events`;
- `signals` row for that signal;
- Stage11C evidence families frozen inside `positions.raw_json`.

No older WD5H cohort rows are joined by symbol or nearest time.

Define **strong entry context** as both:
- Stage11C evidence families with ALIGNED or SUPPORTIVE status >= **3 of 4**;
- signal `decision_context_balance >= 3`.

If enabled by the candidate, strong entry context contributes exactly **+1 continuation vote**.

No future labels, true MFE, final peak, or post-entry external context may be used to form a vote.

## V4.2 base runner-close candidate

Replay the runner component causally:

- runner qualifies once running observed peak >= +1.50%;
- trailing floor = 90% of current running peak;
- V4.2 close candidate occurs after **2 consecutive archived 5s observations** at or below that floor;
- any new running high resets the confirmation count.

This reproduces the runner-close concept of V4.2 but allows a Stage3C4 veto before execution.

## Veto semantics

At a V4.2 close candidate:

1. compute continuation votes;
2. if vote count < candidate threshold -> **ALLOW CLOSE immediately**;
3. if vote count >= threshold -> **VETO CLOSE** and start a fixed **10-second grace window**.

During grace:
- if a new running high occurs, the veto is considered successful; reset the runner trailing state and continue;
- if no new running high occurs, close at the first observation at or after 10 seconds;
- maximum **2 vetoes per trade**; after two successful vetoes, the next V4.2 close candidate is allowed without veto.

These rules are fixed and are not part of the sweep.

## Frozen candidate family

Topology lookback:
- **30s**
- **60s**

Required continuation votes:
- **2**
- **3**
- **4**

Entry-context mode:
- **PATH_ONLY**
- **CONTEXT_BONUS** (+1 vote when strong entry context is true)

Candidate count = 2 × 3 × 2 = **12**.

No additional parameter values may be added after results are inspected.

## Evaluation label

For the final Stage3C4 close signal:

- **PREMATURE_FALSE_REVERSAL** if a later archived observation exceeds the running peak known at signal time;
- **CORRECT_FINAL_REVERSAL** otherwise.

Future labels are evaluation-only.

Retention:
- signal PnL / final archived observed peak.

Also report:
- veto count;
- successful veto count;
- grace-timeout close count;
- which topology/context votes fired at each decision.

## DEV gates

A candidate is eligible only if all hold:

1. signal coverage >= **50%**;
2. precision >= **65%**;
3. premature share <= **35%**;
4. median correct retention >= **80%**;
5. correct signals retaining >=80% >= **50%**;
6. premature close count is strictly lower than V4.2 DEV baseline.

## Ranking

Among eligible DEV candidates:
1. highest precision;
2. lowest premature count;
3. highest >=80 retention share;
4. highest median correct retention;
5. highest coverage;
6. fewer vetoes;
7. shorter lookback;
8. higher required vote threshold;
9. PATH_ONLY before CONTEXT_BONUS on exact ties.

## LATE validation

Freeze exactly one DEV winner and replay unchanged on LATE.

No post-LATE retuning.

## Baselines

Compare against:
- V4.2 runner close;
- Stage3C closest near-miss;
- Stage3C2 highest-precision candidate;
- Stage3C3 highest-precision candidate.

## Decision

If no candidate passes all DEV gates:
- Stage3C4 = **NO PASS**;
- do not relax gates;
- do not proceed to Stage3D.

If at least one passes:
- nominate one frozen candidate for Stage3D integration research only.

Restrictions:
- historical real data only;
- no runtime change;
- no paper/prospective shadow;
- no future labels in decision features;
- market-state context is entry-time static context only.
