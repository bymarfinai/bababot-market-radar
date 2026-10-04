# PP V4-3C — Temporal Reversal Detector Contract

Status: **PREREGISTERED BEFORE CANDIDATE OUTCOME INSPECTION**

Baseline: **Profit Protector V4.2 — Hybrid Protection**

## Objective

Build a causal detector that distinguishes:
- transient runner pullback that later makes a new running high; versus
- genuine final reversal after the final observed running peak.

Stage3C is a detector study only. It does not change position sizing, small-profit reduce architecture, or runtime authority.

## Scope

Primary Stage3C population:
- historical V4.2-triggered trades whose archived 5s observed peak reaches at least **+1.50%**;
- this is the runner-capable regime where Stage3B found an 80% crossing materially more informative.

Small/medium peaks below +1.50% remain for Stage3D adaptive protection and are not used to select the Stage3C runner detector.

## Causal inputs allowed

At each observation the detector may use only information available at or before that observation:

1. current running observed peak;
2. current PnL relative to that running peak;
3. seconds since the last new running high;
4. latest downward PnL velocity;
5. a bounded reclaim-confirmation state built only from observations since a threshold crossing.

Forbidden runtime inputs:
- true clean MFE;
- final observed peak;
- whether a future new high eventually occurs;
- future close or future path labels.

Those forbidden fields may be used only after the fact to score the detector.

## Candidate family

To avoid an unconstrained search, candidates are limited to:

- giveback floor: **90%, 85%, 80%** of current running peak;
- minimum age since last running high: **10s, 20s, 30s, 60s**;
- minimum downward velocity: **0.00, 0.02, 0.03, 0.04 percentage-points/sec**;
- reclaim confirmation wait: **0s, 5s, 10s**.

Reclaim confirmation semantics:
- when floor/age/velocity first qualify, create a pending reversal candidate;
- during the wait window, cancel it if a new running high occurs;
- at the end of the wait, emit REVERSAL only if current PnL remains at or below the candidate floor;
- no future label is used to emit the signal.

No other parameter values may be added after results are inspected.

## Evaluation semantics

For each historical trade:
- replay observations chronologically;
- emit at most one Stage3C REVERSAL signal;
- once emitted, the detector is considered to have closed the runner for evaluation.

Research-only labels:
- **PREMATURE_FALSE_REVERSAL** if the signal occurs before a later higher archived observed peak;
- **CORRECT_FINAL_REVERSAL** if the signal occurs at or after the final archived observed peak;
- **NO_SIGNAL** otherwise.

For correct final reversals calculate:
- gross signal PnL / final archived observed peak;
- whether signal retains >=80% and >=75% of final observed peak;
- seconds final observed peak -> signal.

For premature signals calculate:
- future higher peak magnitude;
- seconds signal -> later higher peak.

## Split and selection

The runner-capable trades are sorted by opened_at_ms.

Use:
- first two chronological thirds as **DEV**;
- final chronological third as **LATE validation**.

Stage3B already inspected the full history, therefore LATE is **not claimed as a pristine untouched holdout**. It is only a chronology robustness check.

Candidate selection is performed using DEV only.

## DEV ranking and gates

A candidate is DEV-eligible only if:

1. emits signals on at least 50% of DEV runner-capable trades;
2. correct-final-reversal precision >= **60%**;
3. premature false-reversal share <= **40%** of emitted signals;
4. among correct final reversals, median gross retention vs final observed peak >= **75%**.

Rank eligible candidates lexicographically by:

1. highest correct-final-reversal precision;
2. highest share of correct signals retaining >=80%;
3. highest median correct-signal retention;
4. highest signal coverage;
5. shorter reclaim wait;
6. shallower parameter complexity:
   - lower age threshold;
   - lower velocity threshold;
   - higher floor.

If no candidate passes all DEV gates, Stage3C must report **NO PASS** and must not invent a relaxed winner after inspection.

## LATE validation

The selected DEV candidate must then be frozen and replayed unchanged on LATE.

Report:
- signal coverage;
- correct vs premature counts;
- precision;
- median correct retention;
- >=80 retention share;
- per-trade outcomes.

No post-LATE retuning is allowed inside Stage3C.

## Baselines

Compare the selected candidate against:

1. V4.2 runner close temporal behavior;
2. naive fixed 90% floor;
3. naive fixed 85% floor;
4. naive fixed 80% floor.

Naive baselines signal on the first eligible floor crossing after running peak >=1.50%, with no age, velocity, or reclaim wait.

## Decision

Stage3C may only nominate a frozen temporal detector candidate for Stage3D.

It must not:
- deploy to runtime;
- enable paper/prospective shadow;
- change V4.2;
- claim prediction of the unknowable final peak.

True MFE/final peak remain scoreboards only.
