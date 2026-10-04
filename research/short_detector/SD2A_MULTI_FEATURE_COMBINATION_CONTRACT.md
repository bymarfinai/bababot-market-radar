# SD-2A — SHORT Archetype-Specific Multi-Feature Combination Contract

Status: **PREREGISTERED / RESERVE SEALED**

## Purpose
Test whether multi-feature T0 combinations can separate SHORT winners from structurally matched SHORT failures better than the single-feature scans from SD-1B / SD-1D.

Research lanes are frozen from prior stages:

- **Lane 0:** provisional winner `SHORT_ARCHETYPE_0` vs frozen `SHORT_LOSS_CLUSTER_0`
- **Lane 1:** provisional winner `SHORT_ARCHETYPE_1` vs frozen `SHORT_LOSS_CLUSTER_1`

Because SD-1C winner clustering missed its preregistered bootstrap-ARI gate, these lanes remain research-only and may not be used as a live router.

## Frozen populations

### Lane 0
- Discovery: 17 WIN / 82 LOSS
- Validation: 8 WIN / 24 LOSS
- Reserve: 5 WIN / 17 LOSS

### Lane 1
- Discovery: 42 WIN / 213 LOSS
- Validation: 19 WIN / 66 LOSS
- Reserve: 8 WIN / 90 LOSS

Sources:
- `research/short_detector/results/sd1a_short_universe_655.csv`
- `research/short_detector/results/sd1c_strong_winner_assignments.csv`
- `research/short_detector/results/sd1d_loss_cluster_assignments.csv`
- raw T0 features: `/opt/core-app/data/wd5h1_thesis_labeled_features.csv`

## Feature hygiene

Use the same frozen SD-1B numeric T0 family:
- 231 raw `f_*` fields
- exclude the seven time / infrastructure-latency fields frozen in SD-1B
- numeric fields only for the exhaustive logistic combination search

No LONG feature subset, coefficient sign, threshold, or regularization value is imported.

## Lane-specific Discovery feature pool

For each lane independently, using **Discovery only**:

1. retain numeric features with >=95% finite coverage in that lane;
2. remove zero-variance features;
3. median-impute from Discovery only;
4. calculate raw one-feature ROC AUC for WIN vs matched LOSS;
5. convert to separation AUC = `max(AUC, 1-AUC)`;
6. rank descending by Discovery separation AUC, lexical feature name as tie-break;
7. greedily select a feature only when absolute Pearson correlation with every already-selected feature is <= **0.85**;
8. stop at **18 features**.

Validation and Reserve do not participate in feature-pool construction.

## Preprocessing

For every lane:
- median imputation fit on Discovery only;
- StandardScaler fit on Discovery only;
- apply the frozen transformation to Validation and Reserve.

## Exhaustive combination search

For the 18 frozen lane features, test **every subset of size 2, 3, and 4**.

Expected subsets:
- C(18,2) = 153
- C(18,3) = 816
- C(18,4) = 3,060
- total = **4,029 subsets per lane**

For every subset, fit class-weighted L2 logistic regression on Discovery only with:

`C ∈ {0.01, 0.1, 1, 10, 100}`

Expected:
- **20,145 fits per lane**
- **40,290 total model fits**

Model:
- solver = `liblinear`
- penalty = L2
- class_weight = balanced
- max_iter = 5,000
- random_state = 4104

## Candidate selection while Reserve is sealed

For each model compute Discovery and Validation ROC AUC.

Freeze exactly one model per lane by:

1. maximize `min(AUC_Discovery, AUC_Validation)`;
2. tie-break by higher Validation AUC;
3. then fewer features;
4. then smaller C;
5. then lexical feature tuple.

Only after the lane winner is frozen may Reserve be evaluated.

No Reserve metric may alter the selected subset, C, signs, or coefficients.

## Diagnostic comparisons

For each lane report:
- best single-feature reference from SD-1D;
- best 2-feature model;
- best 3-feature model;
- best 4-feature model;
- frozen overall D+V model;
- D/V/R AUC;
- coefficients and direction;
- predicted-score distribution by class/split;
- score-target correlation;
- historical realized-PnL enrichment by score quintile as descriptive only.

No probability threshold is tuned in SD-2A.

## Decision gates

For a lane:

### STRONG
- Discovery AUC >= 0.70
- Validation AUC >= 0.70
- Reserve AUC >= 0.70

### PROMISING
- Discovery AUC >= 0.65
- Validation AUC >= 0.65
- Reserve AUC >= 0.65

### WEAK / FAIL
Anything below PROMISING.

A lane may advance to rule extraction / causal routing research only if it is PROMISING or STRONG.

## Integrity

- Reserve is final-check only.
- No threshold or entry rule is tuned here.
- No production or paper runtime changes.
- Paper trading entry pause remains independent.