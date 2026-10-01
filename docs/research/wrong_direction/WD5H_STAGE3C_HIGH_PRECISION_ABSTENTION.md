# WD-5H Stage 3C — High-Precision TAKE/ABSTAIN Frontier

Status: EXECUTED ON VPS core-prod
Authority: RESEARCH ONLY
Production behavior changed: NO

## Goal

Test the final remaining static pre-entry hypothesis:

Even if Stage 3B ranking is weak globally, can the highest-confidence tail
produce a sufficiently pure META_WIN pocket to justify selective trading?

No new model architecture is introduced.

## Primary model

The formal Stage 3B selected architecture remains primary:

BASELINE_UNPURGED_UNWEIGHTED

This prevents post-hoc switching to the purged+weighted model after observing
its slightly better Stage 3B final-test aggregate metrics.

## Model freeze

- model training window: first 60% chronological population;
- hyperparameters: frozen Stage 3B inner-selected top-k/L2;
- threshold selection: Stage 3B outer validation, 60–80%;
- test: final 20%.

The model is not refit after threshold selection. This avoids probability-scale
shift from refitting before applying an absolute threshold.

## Threshold search

Precision floors:

- 50%
- 60%
- 65%
- 70%
- 75%
- 80%

Usable minimum:

- >=10 resolved TAKEs on validation.

Ultra-selective diagnostic minimum:

- >=3 resolved TAKEs.

For each precision floor, Stage 3C chooses the validation threshold with the
largest TAKE count that satisfies the requested precision.

The chosen threshold is then applied unchanged to the test window.

## Important limitation

Stage 3B aggregate final-test performance had already been observed before
Stage 3C.

Stage 3C does not use final-test labels to choose any threshold, but the result
must still be treated as historical robustness evidence rather than a pristine
promotion test.
