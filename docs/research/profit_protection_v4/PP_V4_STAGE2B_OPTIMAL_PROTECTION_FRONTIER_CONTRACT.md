# PP V4-2B — Optimal Protection Frontier Contract

Status: **PREREGISTERED BEFORE SWEEP**

## Question

Given the archived ~5-second price path that was actually observable, which simple causal profit-protection rules improve realized paper PnL and retention without requiring future MFE or future peak knowledge?

Stage2B identifies a **frontier of candidate rules**. It does not promote a runtime rule. Runner-specific policy selection remains Stage2C.

## Frozen cohort

Use all **99** Stage2A clean-label trades.

Ordering:
- chronological by `opened_at_ms`, then `position_id`;
- EARLY+MID = first 66 trades = development set;
- LATE = final 33 trades = untouched holdout for candidate validation.

No trade may be removed based on outcome.

## Causal observation path

Use archived `pp_v3_fast_peak_observations` only within the position lifetime.

At each observation the rule may know only:
- current observed gross PnL;
- running observed peak up to that observation;
- elapsed time / consecutive observations;
- side and entry metadata already known at entry.

The rule may not know:
- future MFE;
- future 5s peak;
- future realized PnL;
- future close time;
- later prices.

## Overlay execution model

Stage2B tests a CLOSE-only protection overlay on top of the historical paper lifecycle.

If a candidate triggers:

1. preserve any historical REDUCE fills that were already executed **before** the trigger;
2. close only the remaining quantity at the trigger observation market price;
3. apply the recorded adverse paper slippage;
4. apply recorded paper exit fee;
5. include allocated entry fees exactly as the paper model does.

If the candidate never triggers, keep the historical actual realized PnL unchanged.

This makes the replay an incremental protection overlay rather than pretending prior reductions never happened.

## Candidate family

A candidate has three causal parameters.

### Arm threshold: observed running gross peak
`arm_pct` in:

- 0.30
- 0.50
- 0.75
- 1.00
- 1.50
- 2.00

### Retention trigger

Once armed, trigger when current observed gross PnL is <= a fraction of the running observed peak.

`retain_ratio` in:

- 0.95
- 0.90
- 0.85
- 0.80
- 0.75
- 0.70
- 0.60
- 0.50

### Confirmation

Require the condition to hold for consecutive archived observations:

`confirm_samples` in:

- 1
- 2
- 3

Total grid: **144 causal candidates**.

No other threshold may be added after seeing the results.

## Evaluation metrics

For each candidate and each split report:

- total simulated realized USD;
- mean / median simulated realized PnL %;
- delta vs actual realized USD;
- win count / win rate;
- trigger count;
- median trigger delay after running peak;
- median retention vs Stage2A executable-net observable peak for trades where that benchmark is >0;
- retention >=80% share;
- retention >=50% share;
- negative-retention share;
- observable-net-peak >=0.50% subgroup metrics;
- runner >=1.00% subgroup metrics;
- runner >=2.00% subgroup metrics.

Future information is allowed only for **evaluation labels**, never for candidate triggering.

## Frontier construction

Development frontier uses only EARLY+MID (66 trades).

A candidate is Pareto-dominated if another candidate is:
- no worse in development total realized USD;
- no worse in development median retention;
- no worse in development runner >=1% median retention;
and strictly better in at least one.

Only non-dominated candidates advance to LATE holdout evaluation.

## Holdout robustness

A frontier candidate is **holdout-positive** only if all are true on LATE:

1. total realized USD > historical actual LATE total;
2. observable-net-peak >=0.50% median retention > historical actual retention for the same subgroup;
3. runner >=1% total realized USD is not below historical actual runner total;
4. no increase in the count of observable-net-peak >=0.50% trades that finish <=0%.

Stage2B does not require 80% retention yet. Its purpose is to locate the feasible static-protection frontier and identify whether runner preservation is the remaining blocker.

## Selection output

Stage2B may name:
- the best holdout-positive candidate by LATE total realized USD;
- the best holdout-positive candidate by LATE >=0.50% median retention;
- the safest runner-preserving candidate.

These are **research references only**.

No candidate receives runtime authority in Stage2B.

## Stage decision

Proceed to **V4-2C Runner Preservation** if:
- at least one candidate is holdout-positive;
- static protection materially improves profit retention;
- runner trade-offs remain visible enough to justify a separate runner policy.

If no candidate is holdout-positive, return to protection feature design rather than deploying a static trailing rule.

## Restrictions

- no runtime change;
- no new REDUCE/CLOSE authority;
- no live trading change;
- no future MFE in triggers;
- no post-hoc grid expansion;
- no using LATE to redefine the grid.
