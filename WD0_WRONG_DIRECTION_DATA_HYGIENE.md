# WD-0 — Wrong-Direction Data Hygiene

Status: IMPLEMENTED IN REPOSITORY  
Scope: cohort/version integrity only. No trading thresholds or live decision rules are changed.

## Goal

Prepare a clean dataset for WD-1 so wrong-direction research never mixes incompatible Stage 11C generations or invents a gate version when metadata is missing.

## Integrity rules

1. The actual position `opened_at_ms` is the cohort boundary timestamp.
2. `positions.raw_json.stage11c_version` is the primary Stage 11C version source because it is copied from the exact gate payload consumed by Stage 13.
3. If position metadata lacks the version, use the latest persisted `entry_revalidations.gate_version` with:
   - `verdict='ENTER'`
   - same `signal_id`
   - `checked_at_ms <= opened_at_ms`
4. A revalidation after the fill is never used.
5. If neither source proves the version, label `fresh_gate_version='unknown'`.
6. `unknown` rows are quarantined from WD-1 directional-model discovery.
7. Current WD-1 primary cohort is `stage11c-v2-evidence-families`. Older known versions remain available as historical comparison cohorts, not mixed into the primary V2 sample.

## Fixes applied

- Cohort schema/version marker bumped to `entry-rebuild-cohort-v2-wd0-integrity`.
- Removed the unsafe implicit default `stage11c-v1-fresh-direction` for POST rows.
- PostgreSQL backfill now reads the earliest position row per signal together with `raw_json`.
- Added a causal ENTER-revalidation fallback.
- Added regression tests for:
  - position metadata attribution,
  - causal revalidation fallback,
  - future-revalidation rejection.
- Added `scripts/wd0_backfill_cohorts.py` to backfill and print:
  - current Stage 11C V2 eligible trades,
  - quarantined unknown rows,
  - other known historical Stage 11C versions.

## Runtime note

Repository implementation is complete, but the Railway Market Radar runtime is currently failed and its Postgres service has no active deployment. Therefore the historical production ledger has not yet been physically relabeled by this stage. Do not claim WD-1 sample counts from production until the backfill runner executes against the restored ledger.

## WD-1 admission rule

Use only rows with a proven `fresh_gate_version`. The primary discovery sample should be:

`POST_ENTRY_REBUILD + stage11c-v2-evidence-families + closed PAPER position`

Keep `unknown` excluded. Keep known V1 rows as a separate comparison cohort.
