# BabaBot Market Radar — Execution Handoff

Status: Stage 9 execution-integration contract.

## Scope

Market Radar does **not** submit Binance orders.

Stage 9 makes the output of Stage 6 consumable by a future risk/execution engine
without changing the detector, scoring, context, MCP, or dashboard layers.

```text
Market Radar
    ↓
LONG / SHORT / NO TRADE
    ↓
execution_intents.json
    ↓
GET /execution/intents
    ↓
future AI / Risk Confirmation
    ↓
future Execution Engine
    ↓
future Binance Order
```

## What becomes an intent

Only:

```text
LONG
SHORT
```

Never:

```text
NO TRADE
```

Each intent is scoped to:

```text
symbol + closed candle timestamp + side
```

Example deterministic ID:

```text
SOLUSDT:1790398199999:LONG
```

## Default safety state

Every Stage 9 intent is created as:

```text
risk_confirmation = PENDING
execution_status  = BLOCKED
executable        = false
```

The following values are intentionally unset:

```text
entry_price = null
quantity    = null
stop_loss   = null
take_profit = null
```

Reason: Market Radar has no frozen production rule yet for entry timing,
position sizing, stop-loss, or take-profit.

Stage 9 therefore does not invent those rules.

## Handoff file

Written atomically after every completed radar scan:

```text
data/execution_intents.json
```

## Read-only API

```text
GET /execution/intents
```

This endpoint exposes the current handoff for a future execution consumer.

There is deliberately no POST/PUT/DELETE execution endpoint and no order route.

## Order submission

```text
live_order_submission_enabled = false
```

Market Radar contains no authenticated Binance order submission path in Stage 9.

Actual live execution requires a separate explicit decision after live
observation validates the Market Radar output and after entry/risk rules are
frozen.
