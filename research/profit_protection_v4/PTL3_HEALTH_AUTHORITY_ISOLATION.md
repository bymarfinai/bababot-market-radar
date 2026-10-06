# PT-L3 — Health Authority Isolation

Status: IMPLEMENTED / VALIDATED / NOT ACTIVATED

## Intent

Stage12 Health remains fully ON for the Stage3C.7A LONG paper experiment:

- health score still runs;
- contradiction analysis still runs;
- MFE/MAE and unrealized PnL still run;
- deterministic Health and fast-guard actions still resolve to HOLD / REDUCE / CLOSE;
- AI arbitration remains available under the existing lifecycle rules.

PT-L3 changes only execution authority for a narrowly qualified prospective cohort.

## Observer-only eligibility

A Health REDUCE/CLOSE is isolated from PAPER order execution only when all are true:

1. PTL3_HEALTH_OBSERVER_ONLY_ENABLED=true;
2. source position is PAPER;
3. source side is LONG;
4. source paper_entry_policy is stage3c7a;
5. an OPEN PT-L2 shadow parent exists for the exact source position;
6. the parent has execution_authority=NONE;
7. all four frozen shadow branches exist;
8. all shadow branches have execution_authority=NONE;
9. at least one protector branch remains OPEN;
10. current shadow parity audit is comparison-eligible.

If any condition is missing, Health keeps its legacy REDUCE/CLOSE authority.

## Health observer ledger

When isolation is active, a Stage12 REDUCE/CLOSE is recorded idempotently in health_observer_decisions with evaluation id, source position, shadow parent, would_action, Health/AI action, score, MFE/MAE/unrealized PnL, hard-risk flag and lifecycle audit context.

The handled evaluation is excluded from list_unacted_lifecycle_actions, so restart/retry cannot later generate a duplicate PAPER exit.

Read-only endpoint: GET /paper/health-observer

Paper summary exposes counts for observer-only decisions, would-reduce, would-close and hard-risk observations.

## Fail-open safety

The experiment never silently removes source safety authority.

If shadow lookup/parity is invalid, Health remains authoritative.

If persisting the observer-only ledger fails after a position qualifies for isolation, PT-L3 records a shadow integrity issue when possible and immediately falls back to the legacy Health PAPER-order path.

When all four protector branches are terminal, Health authority is restored to the still-open source carrier.

## PT-L2 activation interlock

The prospective Parallel Protection Shadow preflight refuses activation unless PTL3_HEALTH_OBSERVER_ONLY_ENABLED=true in addition to the existing Stage3C.7A LONG, paper-only, live-off and shared-boundary requirements.

## Non-goals

PT-L3 does not disable Health, alter Health thresholds/scoring, alter fast-guard formulas, give any protector branch PAPER/LIVE execution authority, enable live trading, or activate the prospective paper epoch.
