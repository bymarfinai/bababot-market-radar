# PS-4 — Shadow Settlement

Status: **COMPLETE / PASS**

Runtime authority: **NONE**

Realtime wiring: **NOT ENABLED**

Settlement version: `ps4-v1-shadow-settlement`

## Objective

Convert PS-3 virtual REDUCE/CLOSE intents into independent virtual branch outcomes without touching the source paper/live position.

Each branch now owns its own:

- remaining quantity
- virtual fills
- fees
- realized PnL
- executable current PnL
- close time / price / reason
- OPEN/CLOSED status

Source paper position authority remains untouched.

## Settlement ledger

PS-4 adds:

`protection_shadow_settlements`

Each row records:

- parent ID
- branch key
- canonical event sequence
- source event ID/time
- intent source
- action
- reason
- requested fraction
- quantity before / executed / after
- market price
- virtual fill price
- allocated entry fee
- exit fee
- realized delta
- cumulative realized PnL
- VIRTUAL_FILLED / VIRTUAL_SKIPPED status

Settlement identity is deterministic and idempotent.

## Protection settlement

PS-3 protection intents supported:

- REDUCE
- CLOSE

A protection REDUCE applies only to that branch.

A protection CLOSE closes only that branch.

One branch settlement never mutates another branch.

## Source lifecycle fallback

PS-4 also recognizes canonical source lifecycle events:

- `SOURCE_POSITION_REDUCE`
- `SOURCE_POSITION_CLOSE`

This is necessary because a protector can remain NO_ACTION until the source strategy itself closes.

### Source REDUCE

Before the first protection divergence:

- source REDUCE is mirrored into the virtual branch.

After the first protection divergence:

- later source partial REDUCE is recorded as `VIRTUAL_SKIPPED`.

This matches the historical overlay semantics: preserve source actions before protector divergence, then let the protector own its branch.

### Source CLOSE

The final source CLOSE always closes any remaining virtual quantity.

If a protection branch already closed earlier, the later source close becomes a no-op/skipped settlement.

## Source fill / fee handling

For source lifecycle actions before divergence:

- actual source fill price can be supplied,
- actual source executed fee can be supplied,
- actual executed quantity can be supplied.

For the source final CLOSE after protection divergence:

- historical/source fill price may still be reused,
- but exit fee is recalculated using the **shadow remaining quantity**.

This detail is required to reproduce V4.2 REDUCE25 economics exactly.

## Protection fill model

Protection-created virtual fills use the frozen research model:

1. side-aware slippage
2. gross PnL on executed quantity
3. pro-rata entry-fee allocation
4. exit fee on virtual fill

No real/paper order is submitted.

## Partial branch accounting

After a partial REDUCE, PS-4 stores:

- realized quantity
- realized PnL
- allocated entry fee
- exit fees already paid
- remaining quantity
- executable unrealized component
- total executable current PnL

For an OPEN partial branch:

> current PnL = realized portion + executable remaining portion

For a CLOSED branch:

> current PnL = final realized PnL

The PS-2.5 UI adapter was hardened accordingly: OPEN branches are ranked using total current PnL, not only partial realized PnL.

## Intent history / restart safety

PS-3 now keeps an immutable-style `intent_history` in branch state.

Example:

```text
event 4 -> REDUCE 25%
event 7 -> RUNNER CLOSE
```

PS-4 can settle both intents later in sequence, even if the process restarted between them.

The existing `virtual_intent` field remains as the most recent intent for UI compatibility.

## Closed-branch event continuity

A branch may close earlier than its siblings.

Closed branches remain passive consumers of future PS-2 canonical events:

- event cursor continues advancing,
- no new protection decision is made,
- realized PnL stays frozen,
- branch remains CLOSED.

This keeps all four branch event sequences aligned while other branches continue.

## Preferred orchestration

Added:

`process_shadow_event_with_settlement(...)`

Flow:

```text
canonical event
  -> PS-3 decision
  -> settle only if:
       - new REDUCE/CLOSE intent, or
       - source lifecycle quantity/status event
```

Ordinary market events return:

`NO_ACTION_REQUIRED`

without rescanning settlement history.

After a partial settlement, PS-3 derives executable current branch PnL from persisted realized + remaining accounting, so mark-to-market stays correct even when no new settlement action occurs.

Also added:

`process_pending_with_settlement(...)`

Recovery behavior:

1. catch PS-3 adapters up once,
2. use persisted intent history,
3. settle once through the latest canonical event.

This avoids O(n²) settlement rescans on dense market streams while preserving restart recovery.

## Read-only API

Added:

`GET /shadow/protection/settlement`

Returns the settlement contract.

Added:

`GET /shadow/protection/settlements?parent_id=...&branch=...`

Returns the virtual settlement ledger for UI/debugging.

No write/mutation endpoint is exposed.

## Unit tests

`tests/test_parallel_protection_shadow_ps4.py`

Coverage includes:

1. virtual-only settlement contract
2. BE0.18 closes only its own branch
3. V4.2 REDUCE25 partial quantity
4. REDUCE -> later runner CLOSE from persistent intent history
5. non-action events skip settlement scan while partial-branch mark stays current
6. idempotent replay
7. closed branch remains passive event consumer
8. source CLOSE fallback
9. source REDUCE before divergence mirrors
10. source REDUCE after divergence skips
11. source CLOSE after protector REDUCE closes remainder
12. fee allocation
13. UI OPEN-partial comparison semantics
14. parity error blocks settlement
15. pending orchestration catch-up
16. SHORT settlement direction
17. execution authority remains NONE

Result:

**17/17 PASS**

Production-image regression:

- PS-4: **17/17 PASS**
- PS-3: **16/16 PASS**
- PS-2.5: **10/10 PASS**
- PS-2: **13/13 PASS**
- PS-1: **10/10 PASS**
- existing Stage7 Read API: **15/15 PASS**
- BE6 regression: **7/7 PASS**

Total:

**88/88 PASS**

## Historical V4.2 economic parity

`research/profit_protection_v4/ps4_historical_settlement_parity.py`

Full frozen 170 cohort was replayed with:

- actual 5s protection observations
- actual source REDUCE fills/fees
- actual source CLOSE fill
- PS-3 V4.2 decision logic
- PS-4 virtual settlement

Result:

- frozen V4.2: **-$100.14766343166144**
- PS-4 replay: **-$100.14766343166133**
- mismatches: **0 / 170**
- exact within 1e-8: **PASS**

This validates both action and economic settlement parity.

## Important causal V4.3 finding

PS-4 also exposed a distinction that must remain explicit.

Frozen V4.3 historical headline:

- **-$43.312886**
- 60 wins / 170
- 35.29% WR

But that frozen result replaced only trades known **ex post** to belong to V4.2 REDUCE25.

The actual forward-causal V4.3 branch cannot know the future lane.

Full170 forward-causal replay:

- PnL: **-$142.229333**
- wins: **60**
- WR: **35.29%**
- changed versus frozen result: **17 trades**
- difference versus frozen PnL: **-$98.916447**

All 17 changed trades are runner lanes:

- RUNNER_CLOSE: **11**
- REDUCE25+RUNNER_CLOSE: **6**
- REDUCE25 target-lane mismatch: **0 / 43**

Therefore:

> the V4.3 component is correct on its frozen 43-trade target, but universal causal deployment can prematurely close future runners.

This is not a PS-4 settlement error. It is a causal routing problem that the prospective shadow experiment must expose.

The same interpretive caution applies to BE historical integration because BE0.18/0.25 was historically substituted into ex-post NO_ACTION trades. Forward BE branches use causal handoff and must be judged prospectively.

## Safety

PS-4 never changes:

- source position status
- source quantity
- Binance order state
- paper order state
- live order state
- execution authority

Every parent/branch remains:

`execution_authority = NONE`

## PS-4 verdict

**PASS**

Settlement mechanics and V4.2 economic parity are validated.

The new V4.3 causal-runner conflict is a strategy-routing finding, not an implementation failure.

## Next

**PS-4.5 — Realtime Protection Shadow UI**

Implement the already-frozen UI:

- one parent trade row
- V4.2 / V4.3 / BE0.25 / BE0.18 columns
- branch OPEN/CLOSED state
- virtual PnL
- delta vs V4.2
- parity badge
- expand branch details
- virtual settlement history

After UI:

**PS-5 — Comparison Dashboard**

for aggregate prospective PnL / WR / LONG-SHORT / lane comparisons.
