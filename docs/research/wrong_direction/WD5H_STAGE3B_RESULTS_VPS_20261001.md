# WD-5H Stage 3B Frozen Results — 2026-10-01

Source of truth: VPS core-prod
Authority: RESEARCH ONLY
Production changes: NONE

## Formal status

META_RANKING_SIGNAL_WEAK

## Data

Stage 3A labels:

- META_WIN: 564
- META_LOSS: 1,327
- TIMEOUT: 284

Binary model population:

- resolved META_WIN + META_LOSS = 1,891

Portable causal pre-entry features:

- 207

## Inner selection

### Baseline

- inner train: 856
- inner validation: 297
- top-k: 5
- L2: 4.0
- inner AP: 0.3903
- inner AUC: 0.5370
- top-10% precision: 36.7%

### Purged unweighted

- inner train after purge/embargo: 828
- removed: 28
- top-k: 10
- L2: 4.0
- inner AP: 0.3906
- inner AUC: 0.5443
- top-10% precision: 40.0%

### Purged + uniqueness weighted

- inner train after purge/embargo: 828
- top-k: 10
- L2: 4.0
- inner AP: 0.3912
- inner AUC: 0.5443
- top-10% precision: 43.3%

Inner results mildly favored purging/weighting, but architecture selection was
not made here.

## Outer validation — architecture selection

Outer validation:

- resolved N: 364
- META_WIN: 112
- META_LOSS: 252
- prevalence: 30.77%

| Architecture | AP | AUC | Top 5% precision | Top 10% precision |
|---|---:|---:|---:|---:|
| Baseline | 0.3620 | 0.5606 | 47.37% | 35.14% |
| Purged | 0.3519 | 0.5423 | 42.11% | 35.14% |
| Purged + uniqueness | 0.3525 | 0.5431 | 36.84% | 37.84% |

The frozen architecture-selection rule therefore chooses:

BASELINE_UNPURGED_UNWEIGHTED

This choice is made before opening final-test results.

## Final untouched test

Final resolved test:

- N: 374
- META_WIN: 93
- META_LOSS: 281
- prevalence: 24.87%

### Formally selected baseline

- AUC: 0.5695
- average precision: 0.2846
- AP lift over prevalence: +3.59 percentage points
- top 5%: 4 / 19 WIN = 21.05%
- top 10%: 11 / 38 WIN = 28.95%
- top 20%: 22 / 75 WIN = 29.33%

This is weak ranking performance and does not support a production gate.

### Purged unweighted — final diagnostic only

- AUC: 0.5859
- AP: 0.2996
- top 5% precision: 31.58%
- top 10% precision: 36.84%

### Purged + uniqueness weighted — final diagnostic only

- AUC: 0.5882
- AP: 0.3026
- top 5% precision: 36.84%
- top 10% precision: 34.21%

The purged/weighted model is somewhat better on the final test, but this cannot
be used to re-select the architecture because outer validation selected the
baseline.

Treating this final-test advantage as proof would be post-hoc selection.

## TIMEOUT score behavior

Final test TIMEOUT N = 61.

Median META_WIN scores:

- baseline: 0.2888
- purged: 0.2676
- purged + weighted: 0.2850

TIMEOUT does not form an obviously isolated high- or low-score class under the
current models.

## Main interpretation

Stage 3A fixed an important target-definition problem, but Stage 3B shows that
this correction alone does not reveal a strong static pre-entry discriminator.

The result is therefore nuanced:

1. meta-labeling is still the correct target formulation;
2. purge/embargo/uniqueness controls are still methodologically necessary;
3. the current 207 pre-entry features provide only weak ranking power;
4. the small final-test improvement of the weighted model is not stable enough
   to promote because outer validation did not select it.

## What this rules out

Do not conclude:

- that more static indicators automatically solve the problem;
- that the weighted model is now the winner because its final test is slightly
  higher;
- that the final test may be used to switch architecture.

## Next

WD-5H Stage 3C — High-Precision TAKE/ABSTAIN Frontier.

Stage 3C is the final test of the static meta-label path.

It should:

1. keep the formally selected baseline architecture as the primary candidate;
2. choose TAKE thresholds only from validation;
3. report precision targets 50/60/65/70/75/80%;
4. require meaningful minimum trade count / coverage;
5. apply the frozen threshold once to final test;
6. show purged+weighted only as a clearly labeled sensitivity;
7. stop the static path if no stable usable high-precision pocket appears.

If Stage 3C fails, the preferred next hypothesis becomes the causal 1–3 minute
confirmation window rather than adding more static pre-entry features.

## Frozen artifact hashes

wd5h3b_meta_model_predictions.csv
SHA256:
5b8f79d55d6d797fd54345c83e53afcf4b4ef36db3b03ec3a2b7d6fab014a752

wd5h3b_meta_model_results.json
SHA256:
1381dd649e3c1c12a22f561c03e0cff12f44749b92f90a875ca60fa7d2ac26bd
