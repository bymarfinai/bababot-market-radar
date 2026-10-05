# PS-2 — Event Fanout & Parity Guard

Status: **COMPLETE / PASS**

Runtime authority: **NONE**

Realtime wiring: **NOT ENABLED**

## Objective

Guarantee that every Parallel Protection Shadow branch receives the exact same canonical market-event stream before any protection logic is allowed to compare performance.

PS-2 does not execute V4.2, V4.3-LS, BE0.25, or BE0.18 logic yet.

It only establishes event integrity.

## Event model

One source event is written once to:

- `protection_shadow_events`

The same event identity is then delivered atomically to all four branches through:

- `protection_shadow_branch_events`

Parity/integrity violations are recorded in:

- `protection_shadow_parity_issues`

Frozen branch set:

1. `V42_BASELINE`
2. `V43_LS`
3. `BE025_CONSERVATIVE`
4. `BE018_AGGRESSIVE`

## Canonical event identity

Every event contains:

- parent ID
- source event ID
- event timestamp
- event type
- market price
- canonical payload
- deterministic SHA-256 event hash
- internal event sequence

Payload JSON is canonicalized with sorted keys, so equivalent payloads produce the same event identity.

## Atomic fanout

For a valid new event:

1. parent must exist and be OPEN,
2. exact four-branch set must exist,
3. source event ID must not conflict with an earlier event,
4. timestamp must not precede the position open,
5. timestamp must not move backward versus the accepted event stream,
6. canonical event is inserted,
7. exactly four branch receipts are inserted,
8. all four branch event cursors are advanced,
9. the transaction succeeds only if receipt count is exactly four.

A partial fanout is not considered valid.

## Sequence rules

Each parent owns its own monotonic internal sequence:

```text
event_seq = 1, 2, 3, ...
```

Distinct events with the same millisecond timestamp are allowed.

They are ordered by accepted arrival sequence.

A process-level fanout mutex prevents concurrent callbacks from racing for the same sequence.

PostgreSQL additionally locks the parent row during fanout.

## Duplicate handling

### Identical duplicate

If the same `source_event_id` arrives with the same canonical hash:

- no second canonical event is created,
- no second receipt set is created,
- result is `DUPLICATE`,
- but only if all 4 original receipts still exist with matching hashes.

### Corrupted duplicate

If the canonical event exists but a receipt is missing or has the wrong hash:

- duplicate is **not** treated as safe,
- result becomes `PARITY_ERROR`,
- issue type: `DUPLICATE_RECEIPT_PARITY_FAILURE`.

### Conflicting duplicate

If the same source event ID arrives with different time/price/type/payload:

- event is rejected,
- issue type: `SOURCE_EVENT_CONFLICT`,
- trade becomes comparison-ineligible.

## Out-of-order handling

If an incoming event timestamp is older than the latest accepted event timestamp:

- event is rejected,
- issue type: `OUT_OF_ORDER_EVENT`,
- comparison eligibility becomes false.

Events before the source-position open time are also rejected:

- issue type: `EVENT_BEFORE_OPEN`.

## Branch-set guard

Fanout requires the exact frozen four-branch contract.

If one branch is missing or an unexpected branch exists:

- no canonical event is accepted,
- issue type: `BRANCH_SET_MISMATCH`,
- comparison is invalid.

## Parity audit

`audit_shadow_parity(parent_id)` compares every branch against the canonical ledger.

For every branch it checks:

- receipt count
- exact sequence
- missing sequences
- extra sequences
- event-hash mismatches

Output includes:

```text
status = PARITY_OK | PARITY_ERROR
comparison_eligible = true | false
```

Any stored integrity issue also makes the trade comparison-ineligible.

This is the contract PS-5/UI will later use to exclude corrupt experiments.

## Authority boundary

PS-2 retains:

```text
execution_authority = NONE
```

It does not:

- submit orders,
- close source positions,
- reduce source positions,
- execute protection decisions,
- change Stage13,
- change live trading.

PS-2 only persists market-event evidence.

## Persistence tables

PS-1:

- `protection_shadow_parents`
- `protection_shadow_branches`

PS-2 adds:

- `protection_shadow_events`
- `protection_shadow_branch_events`
- `protection_shadow_parity_issues`

## Tests

`tests/test_parallel_protection_shadow_ps2.py`

Coverage:

1. one event fans out identically to all four branches
2. identical duplicate is idempotent
3. conflicting duplicate is rejected
4. out-of-order event is rejected
5. same-millisecond events remain sequential
6. pre-entry event is rejected
7. audit detects missing receipt
8. duplicate recheck detects corrupted receipts
9. incomplete branch set blocks fanout
10. parent event streams are independent
11. canonical payload key order does not change identity
12. concurrent same-ms events serialize cleanly
13. execution authority stays NONE

Result:

**13/13 PASS**

PS-1 regression:

**10/10 PASS**

## PS-2 verdict

**PASS**

The project now has a deterministic event-distribution layer where all four protection branches can later consume the exact same market evidence.

No runtime behavior changed.

## Next

**PS-2.5 — UI Data Contract**

Define the API/UI-facing shape before protection adapters are attached.

The contract should expose at minimum:

- parent trade identity
- branch key / label
- branch current state
- parity status
- comparison eligibility
- last event sequence/time
- current MFE / MAE
- current virtual PnL
- branch close status/reason when available
- delta versus V4.2 baseline

After the UI contract is frozen:

**PS-3 — Protection Adapters**

will attach V4.2, V4.3-LS, BE0.25, and BE0.18 to the common PS-2 event stream.
