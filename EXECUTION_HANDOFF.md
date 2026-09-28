# BabaBot Market Radar — Execution Handoff and Guarded Live Path

**Status:** Stage 9 historical handoff contract + Stage 15 current guarded execution architecture.

## 1. Why this document has two execution layers

Market Radar now contains two different concepts that must not be confused:

1. **Stage 9 execution handoff**
   - deterministic JSON/API artifact
   - always non-executable
   - preserved for integration and audit compatibility

2. **Stage 15 guarded live execution**
   - downstream production execution engine
   - can submit authenticated Binance Futures orders
   - only operates after Stage 10/11/12/14 safety layers and explicit live activation

Stage 15 did **not** convert the Stage 9 artifact itself into an executable object.

---

## 2. Stage 9 — Historical safe handoff contract

After every completed radar scan, Market Radar writes:

~~~text
data/execution_intents.json
~~~

Read API:

~~~text
GET /execution/intents
~~~

Only final Stage 6 decisions:

~~~text
LONG
SHORT
~~~

become intents.

NO TRADE is never forwarded.

Each intent is scoped to:

~~~text
symbol + closed candle timestamp + side
~~~

Example:

~~~text
SOLUSDT:1790398199999:LONG
~~~

### Frozen Stage 9 safety state

Every Stage 9 intent remains:

~~~text
handoff_version     = stage9-v1
execution_mode      = HANDOFF_ONLY
risk_confirmation   = PENDING
execution_status    = BLOCKED
executable          = false

entry_price         = null
quantity            = null
stop_loss           = null
take_profit         = null
~~~

The handoff top level also remains:

~~~text
live_order_submission_enabled = false
~~~

This field means:

> The Stage 9 handoff artifact itself cannot submit orders.

It **does not** mean that the current repository has no live-execution subsystem.

That historical statement became incomplete after Stage 15 was implemented.

---

## 3. Current production execution path

Current live-entry flow:

~~~text
Stage 6 LONG / SHORT
        ↓
Stage 10 persisted signal
        ↓
Stage 11 deterministic entry-risk gate
        ↓
Stage 11 / 11B AI supervision
        ↓
final verdict = APPROVE
        ↓
Stage 14 control state
        ↓
Stage 15 live preflight
        ↓
live order queue
        ↓
Binance Futures market entry
        ↓
exchange-side protective stop
        ↓
Stage 12 position lifecycle
        ↓
HOLD / REDUCE / CLOSE
        ↓
Stage 15 reduce-only exit
~~~

A Stage 9 execution_intents.json record is **not** the object that Stage 15 executes.

Stage 15 consumes approved persistent signals and lifecycle state from the database.

---

## 4. Stage 11 entry eligibility

A live entry cannot bypass deterministic Stage 11 risk checks.

The risk gate verifies at minimum:

- LONG/SHORT side is valid
- stage is IGNITION or EXPANSION
- winning Stage 6 score remains at or above 68
- score edge remains at or above 10
- context balance remains positive
- signal price exists
- required context exists
- no hard structural contradiction
- signal is fresh

Only after that gate passes is AI review called.

Final entry verdicts:

~~~text
APPROVE
WATCH
VETO
~~~

Only APPROVE is entry-eligible.

WATCH and VETO never create a new live entry.

AI cannot reverse the original deterministic side.

---

## 5. Stage 14 persistent control plane

Control modes:

~~~text
RUN
PAUSE_ENTRIES
EXIT_ONLY
~~~

RUN:
- new eligible entries may proceed
- lifecycle exits proceed

PAUSE_ENTRIES:
- no new entries
- lifecycle REDUCE/CLOSE remains enabled

EXIT_ONLY:
- no new entries
- lifecycle REDUCE/CLOSE remains enabled

Persistent live activation is a separate state:

~~~text
live_armed = true | false
~~~

New live entries require:

~~~text
mode = RUN
AND live_armed = true
~~~

Live exits do not require ARM and do not require RUN.

---

## 6. Stage 15 live preflight

Endpoint:

~~~text
GET /live/preflight
~~~

A new live entry is blocked unless all required checks pass.

Current checks include:

- LIVE_TRADING_ENABLED is enabled
- Binance API key and secret are configured
- persistent live ARM is enabled
- control mode is RUN
- configured notional does not exceed the hard cap
- paper gate is satisfied
- daily live-loss limit has not been reached
- recent live-loss streak limit has not been reached
- live open-position cap is not full
- Binance account reports canTrade
- hedge mode is not enabled
- sufficient available USDT exists
- no unmanaged Binance exchange positions exist

Entry execution then performs additional checks:

- Stage 11 approval is still fresh
- no managed position for the same symbol already exists
- no exchange position for that symbol already exists
- spread remains inside the configured limit

The system fails closed on any failed entry guard.

---

## 7. Current bounded live defaults

Repository defaults:

~~~text
LIVE_NOTIONAL_USDT                  = 25
LIVE_MAX_NOTIONAL_USDT              = 50
LIVE_MAX_OPEN_POSITIONS             = 1
LIVE_LEVERAGE                       = 1
maximum code-enforced leverage      = 3
LIVE_HARD_STOP_PCT                  = 1.5
LIVE_DAILY_LOSS_LIMIT_USDT          = 10
LIVE_MAX_LOSS_STREAK                = 3
LIVE_MIN_PAPER_CLOSED_TRADES        = 20
LIVE_REQUIRE_PAPER_NET_PNL_NONNEGATIVE = true
LIVE_ENTRY_MAX_AGE_MINUTES          = 10
LIVE_REDUCE_FRACTION                = 0.50
LIVE_MAX_SPREAD_BPS                 = 20
LIVE_BALANCE_BUFFER_MULTIPLIER      = 1.25
LIVE_POLL_SECONDS                   = 10
~~~

These are defaults, not strategy-discovery targets.

Production operators may configure supported values through environment variables, subject to code-enforced bounds.

---

## 8. Live market entry

Stage 15 uses authenticated Binance USD-M Futures APIs.

Before the order:

- spread is checked
- market quantity is rounded to exchange rules
- margin type is set to ISOLATED
- leverage is set to the bounded configured value

Order properties:

- market entry
- deterministic client order ID
- LONG maps to BUY
- SHORT maps to SELL
- duplicate/retry reconciliation queries existing order state by client order ID

The resulting fill is reconciled using Binance user trades when available.

---

## 9. Protective stop is mandatory

Immediately after a successful live entry, the engine calculates and submits an exchange-side protective stop.

For LONG:

~~~text
stop = fill × (1 - hard_stop_pct)
~~~

For SHORT:

~~~text
stop = fill × (1 + hard_stop_pct)
~~~

The stop is rounded to the exchange tick size.

The live position persists the protective-stop price and client/algo identifiers for audit and later cancellation.

---

## 10. Protective-stop failure path

A newly opened live position must not intentionally remain unprotected.

If protective-stop submission fails:

1. Stage 15 immediately attempts a reduce-only emergency market close.
2. If emergency close succeeds:
   - position is persisted for audit
   - position is immediately closed
   - order status records FILLED_EMERGENCY_CLOSED
3. If both protective-stop creation and emergency close fail:
   - order is marked CRITICAL_UNPROTECTED
   - runtime raises a critical error condition

This is a fail-safe path, not normal trade management.

---

## 11. Position lifecycle and exits

Stage 12 evaluates open positions and emits:

~~~text
HOLD
REDUCE
CLOSE
~~~

Stage 15 converts eligible REDUCE/CLOSE lifecycle actions into reduce-only Binance market orders.

Exit handling intentionally differs from entry handling:

- exits are processed before new entries
- exit submission does not require live ARM
- exit submission does not require control mode RUN
- PAUSE_ENTRIES and EXIT_ONLY continue to permit exits
- only live environment + credentials are required for exchange submission

This prevents an operator safety pause from trapping an existing position.

---

## 12. Exchange reconciliation

Stage 15 periodically reconciles persisted LIVE positions against Binance positionRisk.

If a persisted position is already flat at the exchange:

- recent Binance user trades are inspected
- realized PnL and commission are recomputed
- the persisted position is closed with reason exchange_flat_reconciled

The preflight also blocks new entries when Binance contains nonzero positions not managed by the Market Radar LIVE ledger.

---

## 13. Live API surfaces

Read:

~~~text
GET /live/preflight
GET /live/summary
GET /live/orders
GET /live/positions
GET /control/state
~~~

Authenticated mutation:

~~~text
POST /control/state
POST /control/live-arm
~~~

Mutation authentication:

~~~text
X-Baba-Control-Token: <CONTROL_API_TOKEN>
~~~

The token must be configured server-side and match exactly.

---

## 14. Operational interpretation

The correct interpretation of the repository is now:

~~~text
Stage 9:
safe non-executable execution handoff
preserved for compatibility/audit

Stage 15:
separate guarded live-execution engine
explicitly armed
risk gated
paper gated
bounded
reconciled
protective-stop enforced
~~~

Do not use the Stage 9 field live_order_submission_enabled=false as a global indicator of Stage 15 capability.

For exact current execution behavior, source authority is:

1. market_radar/live_trading.py
2. market_radar/live_store.py
3. market_radar/control_state.py
4. market_radar/binance.py
5. tests/test_stage15_guarded_live.py
