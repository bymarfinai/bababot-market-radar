# WD-5H Stage 3A Frozen Results — 2026-10-01

Source of truth: VPS core-prod
Authority: RESEARCH ONLY
Production changes: NONE

## Formal status

META_LABEL_RESET_COMPLETE

## Coverage

- frozen trades: 2,175 / 2,175
- positions: 2,175 / 2,175
- dedicated post-entry 1m paths: 2,175 / 2,175
- minimum primary path points: 30
- minimum 60m path points: 60
- research tests after implementation: 78 / 78 PASS

## Primary triple-barrier result

Frozen rule: net +0.5% / net -0.5% / 30 minutes

| Meta label | N | Share |
|---|---:|---:|
| META_WIN | 564 | 25.93% |
| META_LOSS | 1,327 | 61.01% |
| TIMEOUT | 284 | 13.06% |

Median time to label:
- META_WIN: 7.59 minutes
- META_LOSS: 5.48 minutes
- TIMEOUT: 30 minutes by definition

## Relabeling against WD-1

### CORRECT_RUNNER — 115
- META_WIN: 90 (78.26%)
- META_LOSS: 8 (6.96%)
- TIMEOUT: 17 (14.78%)

### RECOVERED_DRAWDOWN — 385
- META_WIN: 268 (69.61%)
- META_LOSS: 53 (13.77%)
- TIMEOUT: 64 (16.62%)

### RIGHT_THEN_FAILURE — 660
- META_WIN: 160 (24.24%)
- META_LOSS: 381 (57.73%)
- TIMEOUT: 119 (18.03%)

The 160 META_WIN trades are important: they were historical failures but
produced the standardized favorable entry path before invalidation.

### TRUE_WRONG_DIRECTION — 849
- META_WIN: 45 (5.30%)
- META_LOSS: 768 (90.46%)
- TIMEOUT: 36 (4.24%)

The strict true-wrong class maps overwhelmingly to META_LOSS.

### STALL_NO_EDGE — 166
- META_WIN: 1 (0.60%)
- META_LOSS: 117 (70.48%)
- TIMEOUT: 48 (28.92%)

STALL almost never becomes META_WIN.

## Historical realized PnL versus meta label

Historical positive trades:
- N = 507
- 63 become META_LOSS

Historical non-positive trades:
- N = 1,668
- 205 become META_WIN

This directly confirms that historical exit PnL and standardized entry-path
quality are not interchangeable targets.

## Sensitivity

### Net 0.5% / 0.5% — 60m
- META_WIN: 674 (30.99%)
- META_LOSS: 1,418 (65.20%)
- TIMEOUT: 83 (3.82%)
- RIGHT_THEN_FAILURE META_WIN: 200 / 660 = 30.30%
- TRUE_WRONG META_LOSS: 783 / 849 = 92.23%

### Net 1.0% / 1.0% — 30m
- META_WIN: 369 (16.97%)
- META_LOSS: 679 (31.22%)
- TIMEOUT: 1,127 (51.82%)

### Net 1.0% / 1.0% — 60m
- META_WIN: 561 (25.79%)
- META_LOSS: 946 (43.49%)
- TIMEOUT: 668 (30.71%)

The +0.5/-0.5 30m primary resolves 86.94% of events while keeping symmetric
RR and the pre-existing WD-4 economic criterion.

## Outcome-window overlap

Primary event windows:
- median average concurrency: 15.43
- mean average concurrency: 16.28
- maximum concurrent events: 35
- median uniqueness weight: 0.0675
- mean uniqueness weight: 0.0764
- aggregate uniqueness mass: 166.13

Aggregate uniqueness mass is not a literal count of independent observations,
but it shows that 2,175 rows share substantial future price information.

Stage 3B therefore must use:
- purged temporal validation;
- embargo;
- uniqueness-weighted training.

## Conclusion

The label-reset hypothesis is supported.

The new target behaves much more like entry-thesis quality:
- most CORRECT/RECOVERED trades are META_WIN;
- almost all TRUE_WRONG are META_LOSS;
- STALL almost never becomes META_WIN;
- 24.2% of RIGHT_THEN_FAILURE is rescued as META_WIN.

No predictive claim is made yet. Stage 3A establishes the target only.

## Next

WD-5H Stage 3B — Purged Meta-Model + Overlap Uniqueness Weighting

Stage 3B should:
1. join primary meta labels to causal pre-entry features;
2. train META_WIN vs META_LOSS first;
3. keep TIMEOUT separate;
4. purge overlapping label windows;
5. add an embargo around validation/test;
6. train with uniqueness weights;
7. compare against an unpurged/unweighted baseline;
8. leave final test untouched for threshold selection.

## Frozen hashes

wd5h3a_postentry_1m_cache.jsonl
SHA256: 87a10df6ea2aa20607d93e6d000766f68165cdf84e799115a1d0cfc8f2b1ebd3

wd5h3a_triple_barrier_labels.csv
SHA256: 19286dc68408be65bc2a7c683a684e873bd4dd67a552017a39aed4f248d3d1ab

wd5h3a_triple_barrier_results.json
SHA256: 5e2ff54004a6f171f6819e5836f3cbf51cbba1dbbd9cb7b7b45250cabe402a00
