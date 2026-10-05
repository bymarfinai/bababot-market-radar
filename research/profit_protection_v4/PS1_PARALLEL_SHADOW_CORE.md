# PS-1 — Parallel Protection Shadow Core

Status: **COMPLETE**

Runtime authority: **NONE**

Realtime wiring: **NOT ENABLED**

## Objective

Create the safe foundation for prospective champion/challenger profit-protection testing.

One real/paper source position will eventually fan out into four independent virtual protection branches:

1. `V42_BASELINE`
2. `V43_LS`
3. `BE025_CONSERVATIVE`
4. `BE018_AGGRESSIVE`

PS-1 only creates the parent/branch model and persistence boundary.

It does **not** consume realtime market events, execute protection logic, emit paper orders, close positions, or alter the current trading runtime.

## Architecture

A source paper position becomes one immutable shadow parent:

```text
source position
      |
      v
parallel shadow parent
      |
      +-- V42_BASELINE
      +-- V43_LS
      +-- BE025_CONSERVATIVE
      +-- BE018_AGGRESSIVE
```

Every branch starts with exactly the same:

- symbol
- side
- opened timestamp
- entry price
- initial quantity
- initial notional

Each branch then owns isolated mutable state.

Updating one branch cannot overwrite another branch.

## Frozen branch contract

### V42_BASELINE

- role: baseline
- protection family: V4.2 Hybrid
- NO_ACTION BE: none
- REDUCE25 logic: V4.2
- runner logic: V4.2

### V43_LS

- role: challenger
- protection family: V4.3-LS + V4.2 Runner
- NO_ACTION BE: none
- REDUCE25 logic: V4.3-LS
- runner logic: V4.2

### BE025_CONSERVATIVE

- role: conservative challenger
- protection family: V4.3-LS + BE0.25 + V4.2 Runner
- NO_ACTION BE arm: +0.25%
- REDUCE25 logic: V4.3-LS
- runner logic: V4.2

### BE018_AGGRESSIVE

- role: aggressive challenger
- protection family: V4.3-LS + BE0.18 + V4.2 Runner
- NO_ACTION BE arm: +0.18%
- REDUCE25 logic: V4.3-LS
- runner logic: V4.2

## Persistence isolation

PS-1 uses dedicated tables:

- `protection_shadow_parents`
- `protection_shadow_branches`

It does not reuse the canonical `positions` table.

This is intentional.

The existing `positions` table participates in paper/live lifecycle and order execution. Shadow branches must never become accidental order-authority positions.

## Parent identity

A parent is keyed by the canonical source position ID.

A deterministic `parent_id` is derived from that source ID.

Immutable identity includes:

- source position ID
- signal ID
- symbol
- side
- opened time
- entry price
- quantity

Repeated creation with exactly the same identity is idempotent.

Repeated creation with the same source position ID but a different immutable identity is rejected.

This prevents silent experiment corruption after restarts or duplicate callbacks.

## State isolation

Each branch has its own:

- branch instance ID
- branch key
- status
- current state
- remaining quantity
- MFE
- MAE
- future event cursor fields
- branch state JSON
- immutable branch specification JSON

The PS-1 update primitive addresses exactly:

```text
(parent_id, branch_key)
```

so state cannot be shared implicitly between protectors.

## Authority guard

Every parent and branch persists:

```text
execution_authority = NONE
```

The database schema also enforces this value.

PS-1 exposes no order creation API.

It exposes no branch settlement / close execution API.

Therefore PS-1 cannot submit:

- OPEN
- REDUCE
- CLOSE

orders.

## Quantity invariants

The shadow core enforces:

- initial quantity > 0
- entry price > 0
- initial notional > 0
- remaining quantity >= 0
- remaining quantity <= initial quantity

The public branch-state API rejects attempts to increase a branch above its original entry quantity.

This prevents an accidental protection branch from becoming an averaging / add-position mechanism.

## Current state at creation

All four branches begin as:

```text
status = OPEN
current_state = ENTRY_OPEN
remaining_quantity = initial_quantity
mfe_pct = null
mae_pct = null
execution_authority = NONE
```

No protection logic has yet been evaluated.

## Safety boundary

PS-1 is intentionally not imported or called by the current paper-trading execution loop.

The existing Stage13 position remains the source position.

The new shadow tables are dormant until a later stage explicitly wires them.

Therefore completing PS-1 does not change:

- entry behavior
- paper order behavior
- lifecycle CLOSE / REDUCE
- V4.2 authority
- live trading
- current dashboard

## Tests

`tests/test_parallel_protection_shadow_ps1.py`

Coverage:

1. exact four-branch contract
2. identical entry clone across all branches
3. branch-state isolation
4. idempotent parent creation
5. conflicting duplicate identity rejection
6. invalid entry identity rejection
7. authority remains NONE everywhere
8. remaining quantity cannot exceed entry quantity
9. unknown branch cannot be updated
10. separate parents do not share state

Result:

**10/10 PASS**

## PS-1 verdict

**PASS**

The project now has a persistent, isolated, execution-safe parent/branch foundation for Parallel Protection Shadow.

No runtime authority changed.

## Next

**PS-2 — Event Fanout & Parity Guard**

Required behavior:

- one canonical market event enters once,
- the exact same event identity is delivered to all four open branches,
- every branch records the same event sequence,
- duplicate and out-of-order events are deterministic,
- any branch event gap raises a parity failure,
- parity-failed trades are excluded from protector comparison.

PS-2 still should not grant execution authority.

After PS-2:

**PS-2.5 — UI Data Contract**

before protection adapters are wired in PS-3.
