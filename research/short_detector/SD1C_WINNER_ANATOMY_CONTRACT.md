# SD-1C — SHORT Winner Anatomy & Clustering Contract

Status: **PREREGISTERED / RESERVE SEALED FOR CLUSTER FIT**

## Purpose
Determine whether the 99 frozen strong SHORT winners contain multiple reproducible T0 archetypes that can explain why aggregate single-feature rules in SD-1B were unstable.

SD-1C is anatomy only. It does not create an entry rule.

## Frozen universe
Source:
- `research/short_detector/results/sd1a_short_universe_655.csv`
- T0 raw features: `/app/data/wd5h1_thesis_labeled_features.csv`

Strong SHORT winner:
`META_WIN AND historical_max_mfe_pct >= 1.00%`

Expected:
- total strong winners: **99**
- Discovery: **59**
- Validation: **27**
- Reserve: **13**

Only the 59 Discovery strong winners may fit preprocessing, PCA, k-means centroids, or select k.

Validation and Reserve are projection-only / stability checks.

## T0 feature hygiene
Use the same 224 T0 feature universe frozen in SD-1B.

Exclude:
- f_decision_hour_utc
- f_decision_hour_sin
- f_decision_hour_cos
- f_decision_weekday_utc
- f_latency_ai_queue_s
- f_latency_ai_execution_s
- f_latency_stage11c_s

No LONG threshold, feature sign, or archetype label is imported.

## Preprocessing fit on Discovery strong winners only

### Numeric
1. Retain numeric fields with >=95% finite coverage in Discovery winners.
2. Drop zero-variance fields.
3. Median-impute from Discovery winners only.
4. Correlation-prune deterministically at absolute Pearson correlation >0.95:
   - process features in lexical column-name order;
   - retain the first member;
   - drop later highly correlated members.

### Categorical
- One-hot encode levels observed in Discovery winners.
- Unknown Validation/Reserve levels map to all-zero for that categorical family.

### Scaling / PCA
- StandardScaler fit on Discovery winners only.
- PCA fit on Discovery winners only.
- Retain the minimum number of principal components required to explain >=80% cumulative Discovery variance.

## Cluster search
Test KMeans `k = 2..8`, subject to:
- every Discovery cluster has at least 5 winners;
- deterministic `random_state=4104`;
- `n_init=50`.

Primary structure score:
- Discovery silhouette.

Stability diagnostic:
- 100 deterministic 80%-subsample refits for each valid k;
- refit KMeans on the subsample in frozen PCA space;
- assign all 59 Discovery winners to the bootstrap centroids;
- compare against the full-Discovery fit with Adjusted Rand Index;
- report median and 25th percentile bootstrap ARI.

k selection:
1. highest Discovery silhouette among valid k;
2. tie-break by higher median bootstrap ARI;
3. if silhouette differs by <0.01, prefer the smaller k unless the larger k improves median ARI by >=0.10.

This selection is completed before Validation/Reserve cluster composition is inspected.

## Projection
After k is frozen:
- Validation and Reserve winners are transformed with the frozen Discovery imputer/scaler/PCA;
- assign each to the nearest frozen Discovery KMeans centroid;
- do not refit centroids.

## Required anatomy
For each frozen archetype report:
- total and D/V/R winner counts;
- historical MFE median / mean;
- historical realized PnL and positive-realized rate;
- historical WD1 outcome composition;
- top original T0 features separating archetypes;
- flow / momentum / market-relative signatures where supported by observed feature directions;
- D/V/R centroid-distance distribution;
- cluster proportion stability.

## Cancellation test
For representative separating features:
- compare aggregate strong-WIN vs META_LOSS AUC;
- compare each SHORT archetype vs META_LOSS AUC;
- explicitly identify features whose useful direction changes or whose aggregate signal is diluted by opposite archetype behavior.

Loss rows are used only as an external contrast after archetypes are frozen. They do not participate in clustering or k selection.

## Semantic labels
Initial cluster labels must remain neutral:
- `SHORT_ARCHETYPE_0`, `SHORT_ARCHETYPE_1`, etc.

A semantic label such as continuation, counterflow, impulse, recovery, or reversal may be added only if the feature anatomy clearly supports it. LONG labels are not inherited by default.

## Decision gates
SD-1C confirms winner heterogeneity when:
1. selected k >= 2;
2. Discovery silhouette >=0.10;
3. median bootstrap ARI >=0.50;
4. no selected Discovery cluster has <5 winners;
5. the projected Validation and Reserve populations do not collapse entirely into one cluster.

Failure of a gate means clustering remains descriptive / unstable and does not authorize archetype-specific detector work.

## Authority
- Research only.
- No paper or production entry authority.
- Paper trading remains independently paused.