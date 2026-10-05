# PS-5A — Prospective Shadow Runtime Wiring

Status: **IMPLEMENTED / VALIDATED**

Execution authority: **NONE**

Source mode: **PAPER ONLY**

Runtime version: `ps5a-v1-prospective-runtime`

## Objective

Wire the completed PS-1 through PS-4.5 shadow stack into fresh paper-trading lifecycle data without giving the shadow system any order authority.

PS-5A turns the existing research infrastructure into a true prospective experiment:

```text
fresh PAPER OPEN
    |
    +--> one shadow parent
           |
           +-- V4.2
           +-- V4.3
           +-- BE0.25
           +-- BE0.18

Binance aggTrades ----+
                      +--> common PS-2 event ledger
5s protection sample -+
source REDUCE/CLOSE --+
                      |
                      +--> PS-3 decision adapters
                      |
                      +--> PS-4 virtual settlement
                      |
                      +--> PS-4.5 read-only UI
```

The source PAPER position remains authoritative and is never altered by a shadow branch.

## Clean prospective boundary

PS-5A introduces a persistent runtime epoch.

Environment:

- `PROTECTION_SHADOW_RUNTIME_ENABLED`
- `PROTECTION_SHADOW_START_MS`

Persistence:

- `protection_shadow_runtime_epochs`

Rules:

1. exactly one ACTIVE epoch is allowed,
2. a restart reuses the same persistent epoch,
3. changing the configured boundary while an epoch is active returns `BOUNDARY_CONFLICT`,
4. source positions opened before the boundary return `PRE_BOUNDARY`,
5. no historical position is silently backfilled into the prospective cohort.

This provides a hard separation between historical research data and fresh forward paper trades.

## Runtime cursor

Persistence:

- `protection_shadow_runtime_cursors`

Each parent stores:

- epoch
- symbol
- raw feed state
- last aggregate-trade ID
- last aggregate-trade timestamp
- last raw scan timestamp
- last 5s sample timestamp
- last canonical event timestamp
- source closed timestamp
- error count
- last error

Raw feed states include:

- `ACTIVE`
- `NOT_NEEDED`
- `CAPACITY_EXCEEDED`
- `FEED_ERROR`
- `SOURCE_CLOSED`
- `SOURCE_CLOSED_INVALID`

## Paper entry wiring

After Stage13 source OPEN is already persisted and marked FILLED:

1. fetch the created PAPER position,
2. call `register_paper_position`,
3. create one PS-1 shadow parent,
4. create the exact four branch contract,
5. create a runtime cursor.

The hook is fail-isolated.

A shadow registration exception does not roll back or invalidate the source paper entry.

The observer path can register the same source position idempotently on the next 5s cycle if the immediate entry hook was missed.

## Two evidence cadences

PS-5A preserves the frozen research semantics.

### Raw BE evidence

Source:

`GET /fapi/v1/aggTrades`

Canonical event:

`AGG_TRADE`

Used by:

- BE0.18
- BE0.25

Cursoring uses Binance aggregate-trade IDs.

After the first time-bounded fetch, continuation uses:

`fromId = last_agg_trade_id + 1`

This prevents replaying accepted raw trades.

### Observed protection evidence

Source:

existing PP-V4 5-second observer

Canonical event:

`PROTECTION_SAMPLE_5S`

Used by:

- V4.2 small-profit logic
- V4.3-LS
- V4.2 runner logic

No second 5-second scheduler is introduced.

PS-5A piggybacks on the already-running observer.

## Canonical ordering

Before every 5s protection sample:

1. register/recover the parent,
2. catch Binance aggTrades up through the observation timestamp,
3. fan out raw events,
4. append the 5s sample,
5. evaluate all pending events sequentially,
6. settle virtual intents.

Therefore the canonical path is:

```text
raw trades <= sample timestamp
then
5s sample
```

Distinct events at the same millisecond remain valid because PS-2 has a deterministic internal event sequence.

## Batch ingestion

PS-2 adds:

`fanout_shadow_events_batch`

PS-3 adds:

`process_shadow_events_through`

A batch of raw trades is:

- written in one DB transaction,
- delivered 4/4 to every branch,
- evaluated sequentially in memory,
- written back once per branch.

Validation includes a 250-raw-event batch followed by one protection sample:

**251 / 251 events processed in sequence**

This avoids one database transaction per aggregate trade.

## PS-4 settlement optimization

Prospective raw streams may contain thousands of events.

PS-4 was hardened so settlement no longer loads the entire raw-event history on every 5s mark.

Settlement now retrieves only:

- the current mark event,
- protection-intent event sequences,
- source REDUCE/CLOSE lifecycle events.

Existing PS-4 outcome semantics are unchanged.

Regression after this optimization remains PASS.

## Source REDUCE / CLOSE wiring

After Stage13 has already executed and persisted a source REDUCE/CLOSE fill, PS-5A receives:

- action
- source execution timestamp
- reference market price
- actual fill price
- actual executed quantity
- actual fee
- source reason
- deterministic source event ID

Before the lifecycle event is appended, raw aggTrades are caught up through the source execution time.

PS-4 then mirrors the source lifecycle using its frozen branch-isolation rules.

The hook is fail-isolated and cannot roll back the source paper fill.

## Recovery after restart

Paper cycle now runs source-lifecycle reconciliation.

For every active prospective shadow parent it inspects filled PAPER:

- REDUCE orders
- CLOSE orders

A deterministic source event ID is used:

`paper:<order_id>:<action>`

If the event already exists, it is not replayed.

If an executed source lifecycle event was missed, the runtime recovers it.

If recovery occurs after later canonical shadow evidence has already been accepted:

- issue `LATE_SOURCE_LIFECYCLE_RECOVERY` is recorded,
- comparison becomes invalid,
- the lifecycle is still completed so the source/shadow infrastructure does not remain orphaned.

If a source position is CLOSED but no FILLED close order exists:

- issue `SOURCE_CLOSED_WITHOUT_FILLED_CLOSE_ORDER` is recorded,
- the parent is archived,
- comparison remains invalid rather than inventing a fill.

## Parent archiving

A successfully mirrored source CLOSE:

- closes remaining virtual quantities via PS-4,
- archives the shadow parent,
- marks cursor `SOURCE_CLOSED`.

A comparison-invalid source CLOSE is also archived after the lifecycle event is persisted.

Invalid comparison is not allowed to become orphaned runtime state.

## Raw-feed integrity

PS-5A fails closed for comparison on raw evidence problems.

Examples:

- aggregate-trade ID gap
- late raw event after later canonical evidence
- unsafe history retention window
- raw backfill page limit
- provider failure
- raw-feed capacity overflow

An integrity issue is persisted into the PS-2 parity ledger.

Result:

```text
comparison_eligible = false
```

Source paper trading remains unaffected.

The system prefers excluding a shadow experiment over pretending incomplete BE evidence is valid.

## Capacity guard

Environment:

- `PROTECTION_SHADOW_MAX_RAW_SYMBOLS`
- `PROTECTION_SHADOW_RAW_MAX_PAGES`

Defaults:

- maximum raw-enabled concurrent parents: 6
- aggregate-trade page limit: 1000
- maximum pages per catch-up cycle: 5

If raw capacity is exceeded:

1. the parent may still be created,
2. the runtime cursor is marked `CAPACITY_EXCEEDED`,
3. a parity issue is recorded,
4. the trade is excluded from comparison.

The paper position is not rejected.

## Stop raw polling when BE is no longer relevant

Raw aggTrades are needed only while at least one BE branch can still make a BE decision.

Once both BE branches are either:

- terminal, or
- superseded by the active-protector universe,

the cursor becomes:

`NOT_NEEDED`

and subsequent 5s cycles do not call aggTrades for that parent.

V4.2/V4.3/runner monitoring continues on 5s evidence.

## Feed-error behavior

If raw evidence becomes invalid:

- cursor becomes `FEED_ERROR`,
- parity issue is persisted,
- future 5s samples may continue for diagnostics,
- PS-4 blocks comparative settlement while parity is invalid,
- runtime reports `COMPARISON_INVALID`.

This is not treated as a source-paper trading failure.

## Runtime status API

Added:

`GET /shadow/protection/runtime`

Returns:

- runtime version
- configured enabled flag
- configured boundary
- persistent active epoch
- parent count
- active source-parent count
- raw-feed state counts
- feed-error count
- raw capacity
- page limit
- execution authority
- source mode
- raw/sample feed identity

PS-4.5 UI consumes this endpoint.

The Protection Shadow summary now shows:

- runtime ACTIVE / DORMANT
- persistent prospective boundary
- execution authority

## UI impact

The PS-4.5 tab remains read-only.

PS-5A only supplies fresh data to the existing UI contract.

No frontend mutation endpoint was added.

## Startup behavior

When the app starts and PS-5A is enabled:

1. initialize persistence,
2. create/reuse the configured prospective epoch,
3. log epoch status and boundary,
4. start the existing workers.

A boundary conflict affects only the shadow runtime and is visible in status/logs; source paper trading remains isolated.

## Execution authority

Still:

```text
execution_authority = NONE
```

PS-5A never:

- submits Binance orders,
- submits paper orders,
- changes source position quantity,
- changes source close decisions,
- changes Stage12/Stage13 authority,
- changes live positions,
- registers LIVE source positions.

LIVE source mode returns:

`SOURCE_MODE_SKIPPED`

## Validation

### PS-5A core

`tests/test_parallel_protection_shadow_ps5a.py`

Coverage includes:

- clean boundary
- persistent epoch / boundary conflict
- idempotent parent registration
- raw-before-sample ordering
- BE0.18 prospective settlement
- aggregate-trade cursor continuation
- source REDUCE
- source CLOSE + parent archive
- capacity fail-closed
- aggregate ID gap fail-closed
- invalid comparison still archives on source close
- raw polling stops after BE supersession
- 250-event batch
- missed CLOSE recovery after restart
- runtime summary / authority
- LIVE source rejection

Result:

**15/15 PASS**

### Wiring isolation

`tests/test_parallel_protection_shadow_ps5a_wiring.py`

Coverage:

- 5s observer forwarding
- observer shadow error isolation
- paper OPEN registration
- paper OPEN shadow error isolation
- source REDUCE forwarding with actual fill
- source lifecycle shadow error isolation

Result:

**6/6 PASS**

### Existing production-image regression

- PP-V4 observer: **9/9 PASS**
- Stage13 paper trading: **7/7 PASS**
- PS-4: **17/17 PASS**
- PS-3: **16/16 PASS**
- PS-2.5: **10/10 PASS**
- PS-2: **13/13 PASS**
- PS-1: **10/10 PASS**
- Stage7 Read API: **15/15 PASS**
- BE6: **7/7 PASS**

Combined backend validation:

**125/125 PASS**

PS-4.5 UI:

**12/12 PASS**

Combined backend + UI:

**137/137 PASS**

## External feed smoke check

The VPS successfully queried Binance USD-M Futures aggregate trades:

- HTTP 200
- list response
- aggregate trade ID present
- positive price
- positive exchange timestamp
- expected fields available for the PS-5A parser

No private Binance credentials are required for this public market-data feed.

## Activation

The runtime should be enabled only with a fresh boundary after validation.

At activation, record:

- exact `PROTECTION_SHADOW_START_MS`
- runtime endpoint status
- zero or known pre-boundary PAPER positions
- parent count
- authority NONE

Do not move the boundary after the prospective epoch begins.

## PS-5A verdict

**CODE + WIRING VALIDATED / READY FOR CLEAN PROSPECTIVE ACTIVATION**

After activation, the next useful stage is not more historical tuning.

It is:

**PS-5B — Prospective Comparison Metrics**

using only fresh, parity-valid PS-5A outcomes.
