# SD-2B2 — SHORT Single Temporal Feature Scan Contract

Status: **PREREGISTERED / RESERVE SEALED / NO PRODUCTION AUTHORITY**

## Purpose
Search for an interpretable one-feature temporal confirmation rule that separates matched SHORT winners from matched SHORT failures using causal T+1/T+2/T+3 snapshots.

This stage may freeze a research candidate rule, but does not authorize delayed paper/live entry.

## Frozen matched lanes

Lane 0:
- provisional winner SHORT_ARCHETYPE_0 vs frozen SHORT_LOSS_CLUSTER_0
- pre-censor population D/V/R:
  - 17/82
  - 8/24
  - 5/17

Lane 1:
- provisional winner SHORT_ARCHETYPE_1 vs frozen SHORT_LOSS_CLUSTER_1
- pre-censor population D/V/R:
  - 42/213
  - 19/66
  - 8/90

Sources:
- SD-1A frozen universe
- SD-1C winner assignments
- SD-1D loss assignments
- /opt/core-app/data/wd5h4a_temporal_features.csv

## Causal eligibility
A row is eligible at T+N only when:
`primary_label_end_ms > tN_target_ms`
and the temporal snapshot exists.

## Predictor family
For each horizon use numeric fields under:
- confirm_*
- f_micro_*
- f_f_*
- delta_*

Exclude:
- confirm_mfe_pct
- confirm_mae_pct
- target / timestamp fields
- latest-closed timestamps
- OI timestamps / OI age
- confirm_closed_bars
- oi_new_point_since_t0

Expected feature universe:
- **105 temporal predictors per horizon**

MFE and MAE remain anatomy-only to avoid target leakage.

## Candidate rules
For each lane × horizon × feature:
- test every exact Discovery-observed numeric threshold;
- test both one-sided forms:
  - feature >= threshold
  - feature <= threshold
- no bands;
- no feature combinations.

Threshold boundaries are generated from Discovery only.

## Candidate support gates
A threshold is eligible for D/V ranking only if:

Discovery:
- selected >= 5
- rejected >= 5
- WIN recall >= 40%

Validation:
- selected >= 5
- rejected >= 5
- WIN recall >= 40%

The purpose is to prevent tiny high-precision pockets.

## Candidate ranking with Reserve sealed
For each feature:
1. maximize `min(phi_Discovery, phi_Validation)`;
2. tie-break by higher Validation phi;
3. higher minimum D/V recall;
4. fewer selected trades across D+V;
5. lexical rule representation.

For each lane × horizon, freeze the feature/rule with the highest same ranking criteria.

Reserve is opened only after all three horizon candidates for a lane are frozen.

## Lane-level preferred research horizon
Before Reserve is opened:

1. among frozen T+1/T+2/T+3 candidates with
   - phi >= 0.20 in Discovery and Validation
   - recall >= 40% in Discovery and Validation,
   choose the **earliest horizon**;
2. if none meet that D/V quality floor, choose the candidate with highest `min(phi_D, phi_V)`.

Reserve cannot change the preferred-horizon designation.

## Reserve evaluation
For each frozen horizon rule report:
- selected / rejected
- winner captured
- precision
- recall
- phi
- baseline winner prevalence
- precision lift vs baseline
- historical original-entry PnL, descriptive only

## Rule quality tiers
A frozen threshold rule is:

### STRONG
- phi >= 0.25 in D, V, R
- recall >= 40% in D, V, R

### PROMISING
- phi >= 0.15 in D, V, R
- recall >= 40% in D, V, R

### FAIL
Anything below PROMISING.

These are research tiers only.

## Integrity
- No LONG threshold is reused.
- No Reserve metric changes feature, threshold, direction, or horizon preference.
- No PnL participates in candidate selection.
- No multi-feature model.
- No execution replay yet.
- No runtime / paper / production changes.