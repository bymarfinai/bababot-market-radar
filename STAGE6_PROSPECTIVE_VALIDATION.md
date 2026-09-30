[Reading 178 lines from start (total: 178 lines, 0 remaining)]

# Stage 6 Prospective Paper Validation

Status: **DEPLOYED / PROSPECTIVE COHORT RUNNING / ENTRIES ENABLED**


## Active prospective run

- merged to main: `68ab376ddf091acd1e9dd96cf5bd5f8c1762e062`
- Stage 6 version: `stage6-prospective-shadow-v1`
- run ID: `stage6-prospective-1790740200126`
- Stage 6 start ms: `1790740200126`
- discovery cutoff ms: `1790687518406`
- authority: `V3_CONTROL`
- paper entries: **RUN / enabled**
- lifecycle exits: **enabled**
- live trading: **disarmed / env disabled / submission disabled**
- initial cohort state at activation: **0 registered / 0 open / 0 closed**
- summary endpoint: `https://core-prod.43-153-193-103.sslip.io/stage6/summary`

The three Stage 5 adaptive candidates and all three static comparators remain frozen. No tuning is permitted while this prospective cohort accumulates.

## Purpose

Run Stage 6 on genuinely new paper trades without repeating manual historical replay.

The production control remains the existing Stage 12 V3 paper lifecycle. Every paper position opened strictly after the frozen Stage 6 start timestamp is automatically registered into six causal shadow lanes:

- S5-A — primary balanced adaptive protector
- S5-B — runner-preserving adaptive protector
- S5-C — capture-heavy adaptive protector
- STATIC_NET
- STATIC_BALANCED
- STATIC_CAPTURE

This preserves the exact Stage 3–5 comparison contract: shadow lanes use the same entry, quantity, fee and slippage assumptions, process only closed 1-minute candles, and any lane that has not exited by the actual V3 close is right-censored at the exact V3 paper exit.

## Why V3 remains the control

Stage 5 researched the profit-protection layer, not the entire Stage 12 lifecycle. Keeping V3 as the actual paper controller preserves Early Wrong-Direction Guard and Thesis Health while creating a clean, common censor for every candidate.

No shadow action can create, reduce or close a real paper position.

## Frozen candidate parameters

### S5-A

- peak 0.5–2%: no lock
- peak 2–5%: 25% lock
- peak >=5%: 50% lock
- core evidence >=2: +30%
- core evidence >=3: +0%
- adverse OI: +12.5%
- extreme rv15: +2.5%
- action: CLOSE_FIRST

### S5-B

- peak 0.5–2%: no lock
- peak 2–5%: 30% lock
- peak >=5%: 50% lock
- core evidence >=2: +10%
- core evidence >=3: +20%
- adverse OI: +10%
- extreme rv15: +0%
- action: CLOSE_FIRST

### S5-C

- peak 0.5–2%: no lock
- peak 2–5%: 30% lock
- peak >=5%: 50% lock
- core evidence >=2: +25%
- core evidence >=3: +5%
- adverse OI: +12.5%
- extreme rv15: +0%
- action: CLOSE_FIRST

Core evidence is frozen to:

- stale peak >=3m
- adverse 3m return <= -0.10% OR micro-break against position
- opposing taker 45/55

Adverse OI and extreme volatility remain modifiers.

## Persistence

The harness creates isolated tables:

- stage6_validation_trades
- stage6_validation_lanes
- stage6_validation_events

It does not reuse position_evaluations or paper_orders for shadow actions.

The recorder is idempotent and includes restart recovery:

- missing eligible open positions are re-registered from positions
- a control position that closed while the service was restarting is finalized from positions
- shadow policy exits already completed are never overwritten by the V3 censor

## Activation contract

Do not activate until this feature branch is deployed.

While entries are still paused:

1. deploy the tested code
2. set STAGE6_VALIDATION_ENABLED=true
3. set STAGE6_START_MS to a new timestamp taken after deployment
4. set a unique STAGE6_RUN_ID
5. restart and verify /stage6/summary shows zero registered trades
6. only then resume entries

A trade qualifies only when:

opened_at_ms > STAGE6_START_MS

The discovery cutoff remains a hard lower bound.

## Monitoring

GET /stage6/summary

returns:

- registered / open / closed trade counts
- actual V3 aggregate PnL
- S5-A/B/C aggregate PnL
- static comparator PnL
- economic-peak >=2 sample size
- median economic capture
- premature-close rate

This lets the cohort accumulate without manual replay.

## Safety

- feature is disabled by default
- Stage 6 exceptions are isolated from paper execution
- no shadow lane can issue paper orders
- V3 remains paper authority
- production live trading behavior is unchanged
- no Stage 5 parameter may be tuned during Stage 6

## Test record

Isolated Stage 6 tests:

- 8 / 8 PASS

Existing regression suites:

- Stage 12 / Stage 13 / Stage 14 / Stage 7 API: 43 / 43 PASS
- full repository test suite with V5-0 build: 138 / 138 PASS

The code is ready for deployment, but deployment and entry resume are separate operational steps.


## V5-0 sub-1% decision-gate add-on

V5-0 is an optional prospective shadow lane layered onto the existing Stage 6 harness. It only receives positions opened strictly after V5_0_START_MS while V5_0_SHADOW_ENABLED=true.

Frozen V5-0 contract:

- scope: economic MFE >=0.50% and <1.00%
- giveback <30%: HOLD
- giveback 30-50%: WATCH; REDUCE 50% only when danger score >=4
- giveback >=50%: mandatory decision gate
- mandatory score 0-1: HOLD
- mandatory score 2-3: REDUCE 50% (or CLOSE if already reduced)
- mandatory score >=4: CLOSE
- 100% economic giveback from a qualifying peak: hard CLOSE guard
- peak >=1.00%: V5-0 stops intervening; this is the future V5-1 handoff zone

Danger score uses closed 1m information only: adverse 3m momentum +2, micro-structure break +2, opposing taker flow +1, adverse OI confirmation +1.

V5-0 is intentionally not tuned on the historical cohort. Synthetic/historical checks are safety and causality checks only; prospective paper-shadow data is the primary validation source.

[executed on device: core-prod (c128f313-5bdb-41c3-a53a-0590e5cfa134)]