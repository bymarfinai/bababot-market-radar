# WD-5H Stage 4C — High-Precision Temporal Confirmation Gate

Status: EXECUTED ON VPS core-prod
Authority: RESEARCH ONLY
Production behavior changed: NO

## Goal

Convert Stage 4B temporal ranking signal into a selective TAKE / ABSTAIN gate.

Stage 4C does not change the feature model and does not evaluate delayed-entry
economics.

## Frozen model per horizon

For T+1, T+2, and T+3:

- use the fixed Stage 4B diagnostic logistic;
- use the exact Stage 4B train-only top-12 temporal features;
- L2 = 1.0;
- train on the first 60% chronological survivor cohort;
- preserve the survivor guard.

No new hyperparameter search is performed.

## Survivor guard

A candidate is eligible at horizon H only when:

primary_label_end_ms > T0 + H

Therefore a candidate whose original Stage 3A barrier already resolved before
the confirmation timestamp cannot be used to claim confirmation quality.

TIMEOUT remains eligible and is scored operationally.

## Threshold selection

Validation-only precision floors:

- 60%
- 65%
- 70%
- 75%
- 80%

Minimum:

- 10 resolved TAKEs in validation.

For each floor, choose the threshold with the largest resolved TAKE count that
meets the floor.

## Formal horizon selection

Using validation only:

1. highest feasible precision floor;
2. largest resolved TAKE count;
3. lower TIMEOUT rate;
4. shorter delay.

The historical test is never used to switch horizon or threshold.

## Two precision views

Stage 4C reports both:

### Resolved precision

META_WIN / (META_WIN + META_LOSS)

### All-TAKE WIN rate

META_WIN / (META_WIN + META_LOSS + TIMEOUT)

This prevents TIMEOUT candidates from disappearing from the operational
purity calculation.

## Promotion interpretation

Stage 4C historical test is not a pristine promotion test because Stage 4B
already inspected historical test ranking behavior.

Therefore even a strong 4C result remains research evidence.

Fresh prospective validation remains mandatory.
