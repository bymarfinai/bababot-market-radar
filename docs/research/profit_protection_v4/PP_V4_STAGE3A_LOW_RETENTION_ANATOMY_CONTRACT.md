# PP V4-3A — Low-Retention Failure Anatomy Contract

Status: **PREREGISTERED BEFORE FAILURE CLASSIFICATION**

## Objective

Explain why the current V4-2C protector still retains less than 75% of true clean post-entry MFE on many trades.

Stage3A is anatomy only. It does not tune or deploy a new rule.

## Populations

### Primary failure population

All strict-matched trades satisfying:
- clean post-entry MFE > 0%;
- current V4-2C protection action actually fired;
- final protected PnL / clean MFE < 75%.

This population is the direct target for improving current active protection.

### Secondary coverage population

All strict-matched positive-MFE trades with final protected PnL / clean MFE <75%, including NO_ACTION.

This quantifies failures caused by the protector never arming at all.

## Required causal checkpoints

For every primary trade record:
1. true clean MFE;
2. maximum archived 5s observed gross peak;
3. observation capture ratio = observed peak / true MFE;
4. small-reduce trigger timestamp and gross PnL, if any;
5. runner qualification timestamp, if any;
6. runner-close trigger timestamp and gross PnL, if any;
7. final protected net PnL;
8. final true-MFE retention.

## Failure classification

Classification uses the following frozen hierarchy.

### A — OBSERVATION_MISS

Observed 5s gross peak <80% of true clean MFE.

The current observation mechanism itself never exposed the 80%-of-true-MFE target to the protector.

### B — RUNNER_TRIGGER_DELAY

Observed 5s gross peak >=80% of true MFE, runner CLOSE fired, but gross PnL at runner CLOSE trigger <80% of true MFE.

The peak was observable, but giveback/confirmation allowed the decision point to fall below the target.

### C — PARTIAL_REDUCE_DRAG

Observed 5s gross peak >=80% of true MFE, no runner CLOSE fired, a small REDUCE fired, and final protected retention <75%.

The protector saw enough upside, but only locking 25% while leaving the remainder to the old lifecycle lost too much of the peak.

### D — RUNNER_TRANSITION_MISS

True clean MFE >=1.50%, no runner CLOSE fired, and archived observed peak never reached the +1.50% runner qualification threshold.

This is a special transition failure and is reported as a secondary tag. The primary class remains OBSERVATION_MISS when the 80% observability test also fails.

### E — EXECUTION_ACCOUNTING_DRAG

Observed peak and action trigger each reached >=80% of true MFE, but final protected net retention still finished <75%.

This isolates fee/slippage/prior-reduction/accounting drag after an otherwise adequate decision point.

### F — MIXED_OTHER

Any primary failure not captured above.

## Quantitative gaps

For each trade calculate:
- true-to-observed gap, percentage points;
- observed-to-runner-trigger gap when runner close exists;
- runner-trigger-to-final-net gap when runner close exists;
- 80%-target shortfall in final net PnL;
- whether 80% was ever observable at 5s cadence.

## Outputs

- full trade-level CSV for every primary failure;
- JSON summary;
- counts by primary class;
- counts by secondary tags;
- LONG/SHORT breakdown;
- clean-MFE bands;
- top failures ranked by percentage-point shortfall to 80%;
- examples for each class.

## Restrictions

- no new parameter sweep;
- no runtime change;
- no paper/prospective validation;
- no future MFE may be used as a trading decision input;
- true MFE is evaluation/anatomy only.

## Decision into V4-3B

Stage3A must answer:
1. what fraction of active failures are primarily observation-limited;
2. what fraction are runner-trigger/confirmation limited;
3. what fraction are caused by partial-reduce architecture;
4. whether an 80% true-MFE target is even observable often enough to justify Stage3B feasibility work.
