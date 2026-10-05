# PS-3 — Protection Adapters

Status: **COMPLETE / PASS**

Runtime authority: **NONE**

Realtime wiring: **NOT ENABLED**

Adapter version: `ps3-v1-protection-adapters`

## Objective

Attach the four frozen protection systems to the common PS-2 event ledger without changing the PS-2.5 UI contract.

Branches:

1. `V42_BASELINE`
2. `V43_LS`
3. `BE025_CONSERVATIVE`
4. `BE018_AGGRESSIVE`

PS-3 evaluates protection state and emits virtual intents only.

It does **not** settle quantities, close branches, or submit orders.

## Evidence cadence contract

The historical systems were not trained on the same cadence, so PS-3 preserves that distinction.

### Event-driven evidence

`AGG_TRADE`

Used by:
- BE0.18
- BE0.25

BE logic:
1. favorable gross arm is touched,
2. arm only once executable full-close net PnL is >= 0 after configured fees/slippage,
3. close intent only on a **later** raw event where executable net PnL returns to <= 0.

### Observed protection evidence

`PROTECTION_SAMPLE_5S`

Used by:
- V4.2 small-profit protector
- V4.3-LS
- V4.2 runner logic inside every branch

This prevents accidental conversion of the 5s historical rules into raw-tick strategies.

All four branches still receive the same PS-2 canonical event ledger for parity.

## Frozen V4.2 adapter

Small-profit lane:

- arm: +0.50%
- retain: 60%
- confirm: 3 samples
- virtual intent: REDUCE 25%

Runner:

- qualify: +1.50%
- retain: 90%
- confirm: 2 samples
- virtual intent: CLOSE

The small reduce is non-terminal because the historical V4.2 architecture may later transition into runner mode.

## Frozen V4.3-LS adapter

Only the small-profit policy differs from V4.2.

LONG:
- arm: +0.50%
- retain: 97%
- confirm: 1
- full-close intent: 100%

SHORT:
- arm: +0.50%
- retain: 75%
- confirm: 1
- full-close intent: 100%

Runner qualification/close remains the V4.2 1.50 / 90% / 2-sample rule.

## Frozen BE adapters

### BE0.18

- gross arm: +0.18%
- requires executable net PnL >= 0 before arming
- later executable net PnL <= 0 emits CLOSE intent

### BE0.25

Same logic with gross arm +0.25%.

### Integrated lane handoff

BE is intended only for the NO_ACTION universe.

Therefore once the observed 5s protection path reaches +0.50%, the BE state is causally superseded by the V4.3/V4.2 active-protector family.

This preserves the BE5/BE6 integrated architecture:

- NO_ACTION -> BE
- active small-profit lane -> V4.3-LS
- runner -> V4.2

## Cost model

Executable net mark uses parent trade metadata when available:

- initial quantity
- initial notional
- entry fee total
- fee rate
- slippage bps

Fallback defaults match the historical research assumptions:

- fee rate: 0.00075
- slippage: 2 bps

## State written by PS-3

Every branch tracks independently:

- processed event sequence
- logic event count
- lane
- action
- reason
- current gross PnL %
- executable net PnL %
- executable current PnL USDT
- MFE / MAE
- small-protector peak
- confirmation counters
- small-protector fired flag
- runner mode / qualification / confirmations
- BE gross-touch / armed / arm sequence / superseded state
- virtual intent
- decision-terminal flag

These flow through the already-frozen PS-2.5 API shape.

## Virtual intent boundary

PS-3 may emit:

`REDUCE`

or:

`CLOSE`

but the intent explicitly carries:

`settlement_authority = PS4_NOT_AVAILABLE`

PS-3 never changes:

- branch `status`
- branch `remaining_quantity`
- parent position status
- paper/live source position
- execution authority

This is intentionally deferred to PS-4.

## Sequence safety

PS-3 requires every branch to process the exact same event sequence.

If branch adapter cursors diverge:

- `ADAPTER_SEQUENCE_DIVERGENCE`

If an event is skipped:

- `ADAPTER_SEQUENCE_GAP`

The issue is written to the PS-2 parity ledger, making:

`comparison_eligible = false`

Repeated processing of an already-processed event is idempotent.

A catch-up function processes pending canonical events strictly in sequence.

## Read-only adapter contract

Added:

`GET /shadow/protection/adapters`

It exposes frozen adapter settings and evidence-cadence semantics for UI/debugging.

No mutation endpoint is added.

## Unit tests

`tests/test_parallel_protection_shadow_ps3.py`

Coverage includes:

- frozen research parameters
- raw vs 5s evidence separation
- BE0.18 arm/cross
- BE0.25 arm
- executable-net arming requirement
- V4.3 LONG retain97
- V4.3 SHORT retain75
- V4.2 3-sample reduce25
- V4.2 runner precedence / 2-sample close
- BE supersession by active-protector universe
- terminal signal freeze before PS-4
- no settlement/quantity mutation
- adapter idempotence
- sequence-gap invalidation
- sequential catch-up
- PS-2.5 UI compatibility

Result:

**16/16 PASS**

Production-image regression:

- PS-3: **16/16 PASS**
- PS-2.5: **10/10 PASS**
- PS-2: **13/13 PASS**
- PS-1: **10/10 PASS**
- existing Stage7 Read API: **15/15 PASS**
- BE6 regression: **7/7 PASS**

Total:

**71/71 PASS**

## Historical research parity

`research/profit_protection_v4/ps3_historical_parity.py`

The actual frozen evidence was replayed through the PS-3 evaluator.

### V4.2

Population:

**170 trades**

Exact action classification:

- NO_ACTION: 108
- REDUCE25: 43
- REDUCE25+RUNNER_CLOSE: 6
- RUNNER_CLOSE: 13

Mismatch:

**0 / 170**

### V4.3-LS

Frozen replacement cohort:

**43 trades**

PS-3 full-close trigger timestamp versus frozen V4.3 research:

**43 / 43 exact**

Mismatch:

**0**

### BE0.18 + BE0.25

NO_ACTION population:

**108 trades**

Two BE policies:

**216 position-policy comparisons**

Compared against NA-BE2 causal 0ms trigger / cross timestamps.

Mismatch:

**0 / 216**

## PS-3 verdict

**PASS**

PS-3 reproduces the frozen historical protection mechanics exactly on the source evidence used by the research.

This does not yet mean prospective realtime validation has begun.

## Next

**PS-4 — Shadow Settlement**

Consume PS-3 virtual intents and independently settle each virtual branch:

- partial REDUCE fills
- close fills
- branch remaining quantity
- fees
- slippage
- realized + unrealized PnL
- closed status
- close reason/time/price

One branch settlement must never affect another branch or the source paper position.

After PS-4:

**PS-4.5 — Realtime Protection Shadow UI**
