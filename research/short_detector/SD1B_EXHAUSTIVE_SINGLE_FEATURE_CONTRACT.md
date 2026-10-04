# SD-1B — Exhaustive Single-Feature T0 Scan Contract

Status: **PREREGISTERED / RESERVE SEALED**

## Purpose
Test whether any single T0 observable can stably separate the frozen SHORT strong-winner target from non-targets before moving to winner-archetype analysis or multi-feature rules.

## Frozen universe
Source: `research/short_detector/results/sd1a_short_universe_655.csv`

- 655 resolved SHORT candidates
- 99 strong WIN
- 556 non-target
- chronological Discovery / Validation / Reserve = 393 / 131 / 131
- target = `META_WIN AND historical_max_mfe_pct >= 1.00%`

The SD-1A split assignment is authoritative and may not be changed.

## Feature universe
Raw T0 source: `/app/data/wd5h1_thesis_labeled_features.csv`

Use the same *feature-family hygiene* as the LONG discovery methodology, without copying any LONG threshold or feature direction.

From 231 `f_*` fields, exclude seven time / infrastructure-latency fields:
- f_decision_hour_utc
- f_decision_hour_sin
- f_decision_hour_cos
- f_decision_weekday_utc
- f_latency_ai_queue_s
- f_latency_ai_execution_s
- f_latency_stage11c_s

Expected modeling feature universe: **224 T0 features**.

## Candidate scan
Numeric features:
- `x <= threshold`
- `x >= threshold`
- every exact contiguous Discovery-value band `low <= x <= high`

Candidate boundaries come from Discovery only.

Categorical features:
- individual states;
- state subsets when Discovery cardinality <= 8.

No LONG threshold or sign is reused.

## Selection and sealed Reserve
For each feature:
1. Generate candidates from Discovery only.
2. Evaluate Discovery and Validation.
3. Require at least 5 selected and at least 5 unselected in both Discovery and Validation.
4. Freeze the per-feature candidate maximizing `min(phi_Discovery, phi_Validation)`.
5. Only after every feature rule is frozen, evaluate sealed Reserve.

Association metric: phi / point-biserial correlation of selected-vs-not-selected against the strong-WIN binary target.

## Strong-rule gate
A single-feature detector is called STRONG only if its frozen rule achieves:

`phi >= 0.50` in Discovery, Validation, **and** Reserve.

Small-support pockets do not override this gate.

## Required outputs
- exact candidate-rule count;
- numeric/categorical feature counts;
- top frozen features by D+V stability;
- D/V/R selected, captured, precision, recall, phi;
- historical selected PnL and average return as descriptive diagnostics;
- strong-rule PASS/FAIL;
- explicit comparison with the LONG Stage 3C.1 single-feature ceiling;
- reproducible result JSON/CSV.

## Authority
SD-1B is research only. It grants no paper, production, or entry authority.