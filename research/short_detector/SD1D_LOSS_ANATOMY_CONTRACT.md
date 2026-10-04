# SD-1D — SHORT Loss Anatomy & Failure Clustering Contract

Status: **PREREGISTERED / RESEARCH ONLY**

## Purpose
Characterize the 492 frozen SHORT META_LOSS trades independently, then test whether comparing provisional SHORT winner regimes against structurally matching failure regimes materially improves T0 separation versus the aggregate SD-1B problem.

SD-1D does **not** authorize an entry detector or live router.

## Frozen populations

Source:
- `research/short_detector/results/sd1a_short_universe_655.csv`
- T0 raw features: `/opt/core-app/data/wd5h1_thesis_labeled_features.csv`
- provisional winner assignments: `research/short_detector/results/sd1c_strong_winner_assignments.csv`

META_LOSS:
- total: **492**
- Discovery: **295**
- Validation: **90**
- Reserve: **107**

Strong WIN reference:
- total: **99**
- Discovery / Validation / Reserve: **59 / 27 / 13**
- SD-1C winner regimes remain **provisional** because bootstrap ARI missed its preregistered gate.

Only the 295 Discovery META_LOSS rows may fit loss preprocessing, PCA, KMeans centroids, or select k.
Validation and Reserve loss rows are projection-only.

## T0 feature hygiene

Use the same frozen 224 T0 feature family as SD-1B / SD-1C.

Exclude:
- f_decision_hour_utc
- f_decision_hour_sin
- f_decision_hour_cos
- f_decision_weekday_utc
- f_latency_ai_queue_s
- f_latency_ai_execution_s
- f_latency_stage11c_s

No LONG threshold, feature sign, or cluster proportion is imported.

## Independent loss clustering

Preprocessing is fit **only on Discovery META_LOSS**.

### Numeric
1. retain numeric fields with >=95% finite coverage;
2. remove zero-variance fields;
3. Discovery-median imputation;
4. deterministic correlation pruning at |Pearson r| > 0.95:
   - lexical feature order;
   - retain first;
   - drop later correlated members.

### Categorical
- one-hot levels observed in Discovery META_LOSS;
- unseen Validation/Reserve levels map to all-zero for that categorical family.

### Scaling / PCA
- StandardScaler fit on Discovery META_LOSS only;
- PCA fit on Discovery META_LOSS only;
- retain minimum PCs explaining >=80% Discovery variance.

### KMeans search
Test k=2..8:
- random_state=4104;
- n_init=50;
- each Discovery cluster must contain at least **15** losses.

Primary score:
- Discovery silhouette.

Bootstrap stability:
- 100 deterministic 80% subsample refits;
- assign full Discovery loss set to bootstrap centroids;
- compare with full-Discovery labels using Adjusted Rand Index;
- report median and p25 ARI.

k selection:
1. highest Discovery silhouette among valid k;
2. tie-break by higher median bootstrap ARI;
3. when silhouette differs by <0.01, prefer smaller k unless larger k improves median ARI by >=0.10.

Selection occurs before Validation/Reserve composition is inspected.

## Loss-cluster stability gates

Independent SHORT loss heterogeneity is called structurally confirmed only when:
1. selected k >=2;
2. Discovery silhouette >=0.10;
3. bootstrap median ARI >=0.50;
4. every selected Discovery cluster has >=15 losses;
5. Validation and Reserve each project into at least two clusters.

If any gate fails, loss clustering remains descriptive only.

## Mapping loss regimes to provisional winner regimes

Direct matching is attempted only if:
- selected loss k=2; and
- both loss clusters survive projection.

Mapping occurs **after loss clusters and k are frozen**.

Use this preregistered six-feature market signature:
- f_gate_taker_share_for_selected
- f_gate_side_ret_1m_pct
- f_new_flow_support
- f_new_gate_price_x_flow_gap
- f_new_micro_accel_1_vs_3
- f_f_coin_minus_market_15m

For each provisional winner regime and frozen loss cluster:
1. compute Discovery medians for the six features;
2. standardize median vectors using pooled Discovery strong-WIN + META_LOSS robust scale (median / IQR);
3. select the one-to-one assignment minimizing total Euclidean distance.

This mapping is descriptive; it is **not** a live router.

## Within-regime separation scan

After mapping is frozen, compare:
- provisional winner regime A vs mapped loss regime A;
- provisional winner regime B vs mapped loss regime B.

For each of the 224 T0 features:
1. determine numeric/categorical type using the frozen universe;
2. for numeric features, calculate raw ROC AUC on Discovery;
3. freeze the useful direction from Discovery only:
   - raw AUC >=0.5 => HIGH favors WIN;
   - raw AUC <0.5 => LOW favors WIN and use 1-AUC;
4. evaluate Validation and Reserve using the **same frozen direction**;
5. rank features by `min(oriented AUC Discovery, oriented AUC Validation)`;
6. only after ranking is frozen, report Reserve AUC.

No threshold is tuned in SD-1D.

Primary within-regime evidence:
- best D/V stability floor;
- Reserve AUC of the frozen top feature;
- number of features with D/V oriented AUC >=0.60;
- number retaining D/V/R oriented AUC >=0.60.

## Required outputs

- independent loss k-search and bootstrap stability;
- D/V/R loss cluster counts;
- MFE, MAE, historical PnL, and WD1 outcome composition per loss cluster;
- six-feature regime signatures;
- frozen winner↔loss mapping;
- within-regime D/V/R AUC table;
- aggregate-vs-within-regime comparison;
- trade-level loss cluster assignments;
- explicit PASS/NO-PASS verdict.

## Authority

Research only.
No entry, veto, paper, production, or runtime authority.
Paper trading entry pause remains independent of this research.