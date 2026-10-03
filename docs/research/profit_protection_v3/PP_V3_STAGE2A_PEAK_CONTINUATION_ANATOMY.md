# PP-DECISION V3 — Stage 2A Peak / Continuation Anatomy

Status: **COMPLETE — research benchmark only, no production authority**

## Objective

Stage 1 proved that a static trailing floor cannot solve the peak-capture objective. Stage 2A therefore isolates the more fundamental question:

> After a causal observed record peak starts to retrace, what separates a temporary retracement that later continues higher from a terminal observed peak?

This stage does **not** create an exit rule and does not change PP-LEGACY V3, PP-DECISION V2, paper execution, or live execution.

## Frozen dataset

The study reuses the Stage 1 frozen window:

- start boundary: `1790848801393`
- cutoff: `1791021852690`
- observable-arm trades: **1,384**
- arm threshold: **+0.30% observed current PnL**
- fast observation source: `pp_decision_v2_observations`

## Offline event definition

A **record-local-peak candidate** is an observation that:

1. is a new running observed-current-PnL high;
2. is at or above +0.30%;
3. is followed by a lower next fast observation.

Labels are retrospective research labels only:

- **CONTINUED** — at least one later observed current-PnL value exceeds the candidate peak;
- **TERMINAL** — no later observed current-PnL value exceeds the candidate peak.

The terminal label is never available in real time and is used only as the offline target for Stage 2B.

Trades that later finish on a higher rising record without another post-peak retracement are treated as **right-censored**, not forced into TERMINAL.

## Candidate population

- record-local-peak candidates: **5,033**
- CONTINUED candidates: **3,837**
- TERMINAL candidates: **1,196**
- trades with at least one record-local peak: **1,322**
- trades with an observable terminal peak: **1,196**
- right-censored after at least one local peak: **126**
- no record-local peak before close: **62**

So 188 of the 1,384 observable-arm trades do not provide a clean observed terminal-peak event for this anatomy study.

## How close is the observable terminal peak to true MFE?

Among the 1,196 trades with an observable terminal peak:

- median terminal observed peak / true MFE: **90.17%**
- notional-weighted terminal observed peak / true MFE: **88.28%**
- terminal observed peak reaches at least 80% of true MFE in **74.33%** of trades

This is materially better than the Stage 1 static-floor capture result. It shows that, when a clean terminal observed peak exists, the observed stream often contains enough information to get near the economic target.

It does **not** remove the observability problem: some true MFE remains intrapoll and 188 observable-arm trades are censored for terminal-peak anatomy.

## Peak magnitude is not enough

| Observed peak band | Candidates | Terminal | Terminal rate |
|---|---:|---:|---:|
| +0.30% to <+0.50% | 1,289 | 284 | 22.03% |
| +0.50% to <+1.00% | 1,768 | 484 | 27.38% |
| +1.00% to <+2.00% | 1,213 | 271 | 22.34% |
| >=+2.00% | 763 | 157 | 20.58% |

Terminal probability does not increase monotonically with peak size. A peak-size threshold alone is therefore not a credible terminal-peak detector.

## Temporal separation

Metrics below are evaluated at the first fast observation at or after each horizon.

| Horizon | Continued median giveback | Terminal median giveback | Continued median recovery of peak | Terminal median recovery of peak | Terminal still within 20% giveback |
|---|---:|---:|---:|---:|---:|
| T+15s | **6.84%** | **18.78%** | **94.30%** | **86.41%** | **52.82%** |
| T+30s | **5.05%** | **24.32%** | **97.48%** | **88.54%** | **42.23%** |
| T+45s | **4.63%** | **28.63%** | **99.66%** | **89.62%** | **36.21%** |
| T+60s | **4.28%** | **31.73%** | **100.42%** | **90.55%** | **31.60%** |

The separation is strong:

- continuation events usually recover toward the prior peak and increasingly make a higher high;
- terminal events keep a materially larger unrecovered giveback;
- by T+30s, the median terminal event has already given back more than the 20% tolerance implied by an 80%-of-peak capture objective.

### Critical timing implication

At T+15s, median terminal giveback is already **18.78%**.

At T+30s it is **24.32%**.

Therefore a detector that waits for a full 30-second confirmation window cannot preserve 80% of the observed peak on the median terminal event. The current 15-second fast cadence is itself close to the economic boundary.

## Context features

Flow separation is weak at the first 15 seconds:

- T+15s flow-opposite:
  - CONTINUED: **18.92%**
  - TERMINAL: **18.76%**
- T+15s flow-aligned:
  - CONTINUED: **66.20%**
  - TERMINAL: **62.66%**

The difference becomes more visible later:

- T+60s flow-opposite:
  - CONTINUED: **30.40%**
  - TERMINAL: **45.88%**
- T+60s flow-aligned:
  - CONTINUED: **51.40%**
  - TERMINAL: **34.44%**

But by that point terminal giveback is already too large for the 80% capture objective.

Opposite micro-structure and positioning-opposite flags are also more common in terminal events later, but they are too sparse to be standalone early detectors.

## Simple-rule diagnostics

Simple threshold rules are not good enough.

At T+15s:

- giveback >=20%:
  - terminal precision: **42.96%**
  - terminal recall: **47.18%**
  - continued false exit: **19.42%**
- giveback >=15% and not flow-aligned:
  - terminal precision: **41.48%**
  - terminal recall: **22.12%**
  - continued false exit: **9.67%**

At T+30s:

- giveback >=20%:
  - terminal precision: **46.07%**
  - terminal recall: **57.77%**
  - continued false exit: **20.41%**
- giveback >=20% and flow-opposite:
  - terminal precision: **49.30%**
  - terminal recall: **15.20%**
  - continued false exit: **4.72%**

A one-shot giveback threshold or giveback-plus-flow rule cannot separate terminal peaks from future runners with acceptable precision/recall.

## Stage 2A conclusion

**Stage 2A succeeds as an anatomy study.**

The dominant finding is not a magic peak threshold. It is a temporal pattern:

> **CONTINUED peaks recover; TERMINAL peaks fail to recover and their giveback compounds quickly.**

The economic window is narrow. A causal detector must start reacting around the first post-peak observation because waiting to T+30s is already too late for the median terminal trade if the objective is >=80% observed-peak retention.

The next stage should therefore be:

## Stage 2B — Causal Peak Detector Replay

Stage 2B should replay a stateful detector beginning at the first observed retracement after a record peak and evaluate:

- current giveback from causal running peak;
- giveback velocity / time since peak;
- recovery attempt strength;
- near-peak recovery versus persistent failure;
- flow alignment/opposition as supporting evidence, not the primary trigger;
- runner false-exit rate;
- terminal detection before the 20% giveback boundary.

Stage 2B must not use:

- future TERMINAL/CONTINUED labels as inputs;
- final true MFE;
- future observed maximum;
- any information not available at the evaluated observation.

No production threshold is changed by Stage 2A.

## Reproducibility

- script: `research/profit_protection_v3/stage2a_peak_continuation_anatomy.py`
- frozen result: `research/profit_protection_v3/results/stage2a_peak_continuation_anatomy_1791021852690.json`
- tests: `tests/test_pp_v3_stage2a_peak_continuation_anatomy.py`
