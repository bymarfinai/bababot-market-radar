# PT-L2 — LONG Parallel Profit Protector Wiring

Status: IMPLEMENTED / VALIDATED / NOT ACTIVATED

## Scope

PT-L2 prepares the Stage 3C.7A LONG paper cohort for parallel exit-policy
comparison. It intentionally does not change Stage12 Health execution
authority; that is PT-L3.

## Frozen branch set

Every eligible parent uses the exact same paper fill identity and fans out to:

1. V42_BASELINE
2. V43_LS
3. BE025_CONSERVATIVE
4. BE018_AGGRESSIVE

All four branches are virtual and database-enforced with
execution_authority = NONE.

## Production cohort

The prospective runtime accepts only:

- source mode: PAPER
- side: LONG
- paper_entry_policy = stage3c7a
- opened strictly after the frozen prospective boundary

Generic PAPER and SHORT positions are COHORT_SKIPPED.

## Observation contract

There is one canonical 5-second ticker observation stream: PP_V4_STAGE1.

The shadow runtime consumes that stream. It does not create a second ticker
poller. BE lanes may additionally ingest causal Binance USD-M aggTrades
between canonical observations.

Activation is fail-closed unless:

- PAPER_TRADING_ENABLED=true
- PAPER_LONG_DETECTOR_POLICY=stage3c7a
- LIVE_TRADING_ENABLED=false
- PP_V4_STAGE1_ENABLED=true
- PP_V4_STAGE1_START_MS > 0
- PROTECTION_SHADOW_RUNTIME_ENABLED=true
- PROTECTION_SHADOW_START_MS == PP_V4_STAGE1_START_MS

The boundary must never move after the epoch starts.

## Source position

The real Stage13 PAPER position is a market-path carrier only for the parallel
experiment. Each branch has independent virtual quantity, state, actions and
settlement. Branch actions never submit PAPER or LIVE orders.

PT-L3 must remove Stage12 Health/fast-guard REDUCE/CLOSE authority from this
experimental cohort before the prospective epoch is activated.

## PT-L2 acceptance gate

- legacy PS1–PS5A regression suite passes;
- PT-L1 LONG detector and Stage13 regression passes;
- Stage3C7A LONG parent creates exactly four branches;
- all branches inherit the identical source entry fill and initial quantity;
- generic and SHORT parents are excluded;
- 5-second observer/shadow boundaries must match exactly;
- branch execution authority remains NONE;
- shadow runtime remains disabled by default.
