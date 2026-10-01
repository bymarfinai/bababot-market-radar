# WD-5B VPS Frozen Results — 2026-10-01

Source of truth: VPS `core-prod` frozen WD-5A dataset.  
Authority: research only.  
Production rule changes: none.

## Executive result

**WD-5B did not find a robust causal pre-entry discriminator.**

Current Stage 4/5/6/11C entry-state features are not sufficient to reliably classify the 435 trades that should be reversed versus the 386 trades that should be skipped.

This is a negative research result, but it is highly informative: it prevents promotion of a Direction Gate V2 based on unstable in-sample correlations.

## Primary portable logistic model

Inner chronological model selection:

- selected raw features: 5
- L2: 4.0
- inner-validation AUC: **0.622**

Selected features:

1. Stage11C family combination
2. median absolute 5m return
3. context taker-buy share
4. context taker buy/sell ratio
5. selected-side momentum score component

Performance:

| Window | AUC | Balanced accuracy |
|---|---:|---:|
| Inner validation | 0.622 | 0.551 |
| **Outer validation** | **0.509** | **0.504** |
| Final untouched test | 0.599 | 0.551 |
| Novel-symbol final subset | 0.504 | 0.511 |

The model loses almost all ranking ability on the outer validation window.

## Full-causal logistic sensitivity

Including time / latency / raw-scale features does not solve the problem.

| Window | AUC |
|---|---:|
| Inner validation | 0.602 |
| **Outer validation** | **0.511** |
| Final test | 0.606 |
| Novel symbols | 0.533 |

The additional potentially nonportable features therefore do not create a robust edge.

## Nonlinear shallow forest

The nonlinear model looks somewhat stronger during model selection:

- inner-validation AUC: **0.630**
- selected top-k: 40
- depth: 4
- min leaf: 25

But it fails the next chronological window:

| Window | AUC | Balanced accuracy |
|---|---:|---:|
| Inner validation | 0.630 | 0.582 |
| **Outer validation** | **0.479** | **0.455** |
| Final test | 0.638 | 0.614 |
| Novel-symbol test | 0.619 | 0.611 |

The final-test rebound cannot override the outer-validation failure. This pattern indicates substantial time/regime instability rather than a stable classifier.

## Stability-selected feature models

WD-5B also selected 24 features that remained present across all three DEV chronological blocks.

Examples:

- Stage11C family combination
- OI interpretation
- structure status
- taker share
- selected-side momentum
- 5m selected-side return
- selected score / score edge
- regime family

Results:

| Model | Outer validation AUC | Final test AUC |
|---|---:|---:|
| Stable logistic | **0.477** | 0.616 |
| Stable forest | **0.476** | 0.612 |

Stability filtering therefore does not repair the outer-window collapse.

## Action-threshold failure

No tested model could achieve even a **60% precision floor for BOTH actions** on outer validation.

In other words, there was no outer-validation threshold pair where both:

- REVERSE decisions were at least 60% correct, and
- NO TRADE decisions were at least 60% correct.

Some final-test thresholds show high REVERSE precision, but those same thresholds were not reliable in the immediately preceding outer-validation window.

They are therefore not promotion-grade.

## Core information-gap diagnosis

The most important WD-5B finding is structural.

Across the 821 primary trades:

### Stage 4 opposite-side score is mostly absent

- opposite score = 0: **789 / 821 = 96.10%**
- opposite momentum component = 0: **96.10%**
- opposite activity component = 0: **98.29%**
- opposite persistence component = 0: **100%**
- opposite timeframe-consistency component = 0: **100%**

So although Stage 4 computes independent LONG and SHORT scores in code, in this admitted wrong-direction population the raw momentum architecture gives almost no live evidence to the opposite side.

### Stage11C is conditioned on the selected side

For all 821 trades that entered:

- PRICE_STRUCTURE family = ALIGNED: **821 / 821**
- ret3 aligned = TRUE: **821 / 821**
- ret3 opposite = FALSE: **821 / 821**
- opposite micro-structure = FALSE: **821 / 821**

This is expected from the current Stage11C admission logic: price-family opposition cancels the entry and non-aligned price waits.

As a consequence, the dataset presented to a pre-entry classifier is mostly a description of:

> why the already-selected side is admissible

rather than:

> whether an economically attractive opposite / reversal thesis exists.

## Feature effects are real but not stable enough

Some features show modest descriptive separation.

Examples:

- family combination
- selected-side momentum component
- selected-side 5m return
- structure state
- OI interpretation
- taker flow

But category rates shift materially between chronological blocks.

Example: Stage11C
`ALIGNED|ALIGNED|ALIGNED|ALIGNED`

- full reverse rate: 67.2%
- chronological block reverse rates:
  - 78.6%
  - 53.8%
  - 46.7%
  - 72.7%
  - 85.7%

That is useful evidence of regime dependence, not a stable standalone reverse rule.

## Formal WD-5B conclusion

Machine-readable status:

`NO_ROBUST_PREENTRY_DISCRIMINATOR`

Outer-validation AUCs:

- portable logistic: 0.509
- full-causal logistic: 0.511
- portable nonlinear forest: 0.479
- stable logistic: 0.477
- stable forest: 0.476

Best outer-validation AUC: **0.511**

No model reached a two-sided 60% precision floor.

## What this means for the 849-trade target

WD-4 remains valid:

- 463 / 849 have a strict WIN-capable resolution path
- 386 / 849 map to NO TRADE

But WD-5B shows we **cannot yet identify those groups reliably at entry using the current feature space**.

Therefore we must not convert the WD-4 hindsight labels directly into a production REVERSE / NO TRADE rule.

## Handoff implication

The next stage should not yet be a production Direction Gate V2.

The next research step should reconstruct **symmetric counter-direction / reversal-thesis evidence** at the same causal decision time.

The core missing question is not:

> Is the selected side currently aligned?

Stage11C already answers that.

It is:

> Is this aligned move becoming overextended / exhausted such that the opposite direction has a better bounded-risk payoff than continuing with the selected side?

That requires new causal features specifically designed for reversal propensity before a new classifier is attempted.
