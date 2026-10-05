# PS-2.5 — Parallel Protection Shadow UI Data Contract

Status: **COMPLETE / PASS**

Runtime authority: **NONE**

UI implementation: **NOT YET ENABLED**

Contract version: `ps2.5-v1-shadow-ui-contract`

## Objective

Freeze the backend-to-UI contract before PS-3 attaches the four protection engines.

The goal is to avoid changing frontend structure every time a protection adapter becomes available.

PS-2.5 therefore provides:

- stable branch names and order,
- stable parent/market/parity/comparison/branch object shape,
- explicit nullable fields for PS-3/PS-4 data that does not exist yet,
- read-only API endpoints,
- exact dashboard placement and table semantics.

No protection logic is executed by PS-2.5.

## Read-only API

### Contract metadata

```text
GET /shadow/protection/contract
```

Returns:

- contract version
- branch order
- branch labels
- baseline branch
- frozen protector configuration
- fields intentionally nullable until later stages

### Position snapshot

```text
GET /shadow/protection/positions
```

Optional query filters:

- `limit` — 1..500
- `status` — OPEN / ARCHIVED
- `symbol`
- `side` — LONG / SHORT

Example:

```text
GET /shadow/protection/positions?status=OPEN&side=LONG&limit=100
```

This endpoint is read-only.

## Frozen branch order

1. `V42_BASELINE` — UI label `V4.2`
2. `V43_LS` — UI label `V4.3`
3. `BE025_CONSERVATIVE` — UI label `BE0.25`
4. `BE018_AGGRESSIVE` — UI label `BE0.18`

Baseline comparison branch:

```text
V42_BASELINE
```

The order is part of the UI contract and should not depend on alphabetical database ordering.

## Top-level snapshot shape

```json
{
  "contract_version": "ps2.5-v1-shadow-ui-contract",
  "generated_at_ms": 0,
  "execution_authority": "NONE",
  "baseline_branch_key": "V42_BASELINE",
  "branch_order": [
    "V42_BASELINE",
    "V43_LS",
    "BE025_CONSERVATIVE",
    "BE018_AGGRESSIVE"
  ],
  "count": 1,
  "comparison_eligible_count": 1,
  "comparison_ineligible_count": 0,
  "filters": {},
  "positions": []
}
```

## Position object

Every UI row corresponds to **one source trade**, not one branch.

A position contains five logical areas:

### 1. parent

Immutable source-trade identity:

- parent ID
- source position ID
- signal ID
- symbol
- side
- status
- opened timestamp
- entry price
- initial quantity
- initial notional

### 2. market

Shared canonical PS-2 observation:

- event version
- latest event sequence
- latest source event ID
- latest event timestamp
- current market price
- gross directional move from entry
- gross mark PnL

Important:

> `market.gross_mark_pnl_usdt` is not a protector result.

It is shared market context only.

### 3. parity

Experiment integrity:

- `status` — PARITY_OK / PARITY_ERROR
- `comparison_eligible`
- canonical event count
- issue count
- issue types
- branch-complete flag

A trade with:

```text
comparison_eligible = false
```

must not enter comparative performance statistics.

### 4. comparison

Parent-level comparison metadata:

- baseline branch
- whether all four branch performance values are ready
- current best branch
- current best delta versus V4.2

Before PS-3/PS-4 branch PnL is available:

```json
{
  "performance_ready": false,
  "current_best_branch_key": null,
  "current_best_delta_vs_v42_usdt": null
}
```

### 5. branches

Exactly four ordered branch snapshots.

## Branch object

Each branch exposes:

### identity / display

- branch key
- label
- short label
- display rank
- category
- role
- protection family

### frozen protector config

- NO_ACTION BE arm
- REDUCE25 logic
- runner logic

This lets UI show the real config being compared, rather than only a nickname.

### runtime state

- status
- current state
- execution authority

### telemetry

- last event ID
- last event time
- last event sequence
- MFE
- MAE
- remaining quantity

### decision

Reserved stable shape:

- lane
- action
- reason
- BE armed
- runner qualified
- reduce triggered

These are nullable until PS-3.

### performance

Reserved stable shape:

- `available`
- current PnL USDT
- current PnL %
- realized PnL USDT
- realized PnL %
- delta vs V4.2 USDT

The UI adapter computes `delta_vs_v42_usdt` from the common baseline when branch PnL exists.

PS-3 does not need to duplicate comparison arithmetic into each branch.

### settlement

Reserved stable shape:

- closed timestamp
- close price
- close reason

These remain nullable until shadow settlement exists in PS-4.

## Dashboard placement

Current terminal order begins:

```text
Positions
Open Orders
Order History
Position History
...
```

The future PS-4.5 UI placement is frozen as:

```text
Positions
Protection Shadow
Open Orders
Order History
Position History
...
```

Protection Shadow must not replace the current Positions screen.

The existing Positions tab remains the canonical source-position / lifecycle view.

## Protection Shadow main table

One source trade = one row.

Recommended frozen column concept:

| Symbol | Side | Entry | Mark | Parity | V4.2 | V4.3 | BE0.25 | BE0.18 | Best / Δ vs V4.2 |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |

The four protector cells should show, when available:

- OPEN / CLOSED state
- virtual PnL
- close indicator

Do not create four duplicate trade rows.

## Expand detail

Clicking one parent row should expand a four-branch comparison inspector.

Each branch detail uses the same stable dimensions:

- branch name
- protection family
- current state
- lane
- action
- BE / REDUCE / runner flags
- MFE / MAE
- remaining quantity
- PnL
- delta vs V4.2
- virtual close time
- virtual close price
- close reason

Parity errors should be visible at parent level before branch performance.

## Aggregate UI is intentionally deferred

PS-2.5 does **not** define final aggregate WR/PnL dashboard metrics.

Those belong to:

**PS-5 — Comparison Dashboard**

because aggregate metrics require completed shadow settlement.

PS-2.5 only freezes the trade-level data contract needed to build that later without schema churn.

## Current-data behavior before PS-3

At PS-2.5:

- parent identity is available,
- shared market observation is available,
- parity status is available,
- branch config/state is available,
- MFE/MAE may be null,
- branch PnL is null,
- branch actions are null,
- settlement is null,
- best branch is null.

This is intentional.

The API must not manufacture protector performance from shared mark-to-market movement.

## Comparison readiness

Parent:

```text
comparison.performance_ready = true
```

only when all four branch performance values are available.

When ready:

- branch delta versus V4.2 is derived automatically,
- best current branch is derived automatically,
- best delta versus V4.2 is derived automatically.

## Safety

Every UI response carries:

```text
execution_authority = NONE
```

The endpoints are GET/read-only.

PS-2.5 does not:

- create shadow parents,
- write market events,
- execute a protection decision,
- issue REDUCE/CLOSE,
- modify source positions,
- change Stage13,
- change live trading.

## Tests

`tests/test_parallel_protection_shadow_ps25.py`

Coverage:

1. frozen branch order and labels
2. one parent / four ordered branches
3. market observation separated from protection performance
4. frozen protector configs
5. future PS-3 state fields flow through stable shape
6. delta versus V4.2 and best branch derivation
7. parity failure disables comparison eligibility
8. filters normalize and apply
9. SHORT gross movement semantics
10. execution authority remains NONE

Result:

**10/10 PASS**

Frontend fixture:

`results/ps25_ui_contract_example.json`

The fixture contains one synthetic parent with all four branches and populated example performance fields so frontend work can begin before realtime PS-3 data exists.

Regression in the production app image:

- PS-2.5: **10/10 PASS**
- PS-2: **13/13 PASS**
- PS-1: **10/10 PASS**
- existing Stage7 Read API: **15/15 PASS**
- BE6 regression: **7/7 PASS**

Total validation in that run:

**55/55 PASS**

## PS-2.5 verdict

**PASS**

The backend/UI shape is now frozen before protection adapters are attached.

## Next

**PS-3 — Protection Adapters**

Attach the four existing protection systems to the common PS-2 event stream while preserving the PS-2.5 response shape:

- V4.2 baseline
- V4.3-LS challenger
- BE0.25 conservative
- BE0.18 aggressive

PS-3 should populate:

- decision state
- MFE / MAE
- current virtual PnL
- protection flags

without changing the UI contract.

After protection logic and settlement are complete:

**PS-4.5 — Realtime Protection Shadow UI**

will implement the frozen tab/table/inspector design.
