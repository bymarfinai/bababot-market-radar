# BabaBot Market Radar — MCP and HTTP Interface

**Status:** Stage 7 MCP contract remains active; the surrounding HTTP service has expanded through Stage 15.

## 1. Architecture

The MCP layer is still a **read-only inspection surface** over deterministic Market Radar output.

~~~text
Market Radar deterministic engine
        ↓
latest_scan.json
        ↓
read-only MCP tools
        ↓
AI / MCP client inspection
~~~

The broader HTTP service now also exposes persistence, paper, lifecycle, live-status, and authenticated control endpoints.

Important distinction:

> MCP itself remains read-only.  
> The HTTP service as a whole is no longer read-only because Stage 14/15 added authenticated control mutations.

Market Radar has no runtime dependency on BabaBot Discovery.

---

## 2. MCP endpoint

~~~text
POST /mcp
~~~

Production backend:

~~~text
https://market-radar-production-d307.up.railway.app
~~~

MCP endpoint:

~~~text
https://market-radar-production-d307.up.railway.app/mcp
~~~

Protocol revision:

~~~text
2025-11-25
~~~

The MCP server is stateless and reads the latest deterministic radar snapshot.

---

## 3. MCP tools

Exactly three MCP tools are exposed.

### get_market_radar

Arguments: none.

Returns a compact current-radar view including:

- scan timestamps
- market universe/completion counts
- moving candidate count
- IGNITION / EXPANSION / EXHAUSTION counts
- LONG / SHORT / NO TRADE counts
- compact candidate list

### get_moving_coins

Optional filters:

~~~text
decision = LONG | SHORT | NO TRADE
stage    = IGNITION | EXPANSION | EXHAUSTION
~~~

Returns current moving candidates after filtering.

### inspect_symbol

Required:

~~~text
symbol
~~~

For a current moving candidate, returns:

- stage
- deterministic final decision
- LONG_SCORE / SHORT_SCORE
- score gap / edge
- 5m / 15m / 1h / 24h returns
- movement/activity ratios
- structure
- taker flow
- raw OI context
- funding
- market regime
- decision reasons

For a non-moving symbol, returns the latest Stage 1 market snapshot when available.

---

## 4. MCP scope boundary

MCP does **not**:

- trigger a Binance rescan
- calculate movement state
- classify IGNITION / EXPANSION / EXHAUSTION
- recalculate LONG_SCORE / SHORT_SCORE
- reinterpret Open Interest
- calculate market regime
- change Stage 6 LONG / SHORT / NO TRADE
- call Stage 11 AI approval
- open or close positions
- arm live trading
- change control mode
- submit Binance orders

All source-of-truth calculations remain in the production engine.

---

## 5. Core radar HTTP endpoints

~~~text
GET /health
GET /radar/latest
GET /radar/candidates
GET /radar/symbol/{symbol}
GET /market/klines
~~~

These support dashboard and operational inspection.

---

## 6. Historical Stage 9 handoff endpoint

~~~text
GET /execution/intents
~~~

This returns the non-executable Stage 9 HANDOFF_ONLY artifact.

It is not the Stage 15 live-order queue.

See EXECUTION_HANDOFF.md.

---

## 7. Persistence and signal-history endpoints

~~~text
GET /history/summary
GET /history/signals
~~~

Supported signal filters include symbol, side, and limit.

Actionable Stage 6 LONG / SHORT signals are persisted; NO TRADE is not part of the actionable signal ledger.

---

## 8. AI approval endpoints

~~~text
GET /approval/summary
GET /approval/reviews
GET /approval/models
GET /approval/models/summary
~~~

These expose:

- deterministic risk-gate results
- final APPROVE / WATCH / VETO results
- model roles
- provider/model verdicts
- confidence
- latency
- model errors

They are inspection endpoints only.

---

## 9. Position lifecycle endpoints

~~~text
GET /positions/open
GET /positions/evaluations
~~~

Position evaluations may expose:

- current price
- unrealized PnL %
- MFE / MAE
- health score
- deterministic HOLD / REDUCE / CLOSE
- AI position action
- final lifecycle action
- hard-risk flag
- current context snapshot

---

## 10. Paper-trading endpoints

~~~text
GET /paper/summary
GET /paper/orders
~~~

Paper data includes executed order history, position outcomes, win rate, fees, and net PnL.

---

## 11. Stage 15 live endpoints

Read:

~~~text
GET /live/preflight
GET /live/summary
GET /live/orders
GET /live/positions
~~~

The live preflight reports current guard state such as:

- live env enabled
- credentials available
- live armed
- control mode
- paper gate
- daily live PnL
- recent loss streak
- configured notional/cap
- leverage
- hard stop
- available USDT
- position mode
- unmanaged exchange positions
- pass/fail reasons

---

## 12. Stage 14/15 control endpoints

Read state:

~~~text
GET /control/state
~~~

Authenticated mutations:

~~~text
POST /control/state
POST /control/live-arm
~~~

Required header:

~~~text
X-Baba-Control-Token: <CONTROL_API_TOKEN>
~~~

POST /control/state accepts:

~~~json
{
  "mode": "RUN | PAUSE_ENTRIES | EXIT_ONLY",
  "note": "optional"
}
~~~

POST /control/live-arm accepts:

~~~json
{
  "armed": true,
  "note": "optional"
}
~~~

ARM LIVE performs exchange-aware preflight before changing the persistent arm state to true.

DISARM does not disable risk-reducing live exits.

---

## 13. Health endpoint

GET /health exposes discoverable service routes and whether a control token is configured.

It does not expose the secret token value.

---

## 14. Dashboard relationship

The dashboard is a static client.

Current architecture:

~~~text
Vercel static dashboard
        ↓ HTTP
Railway Market Radar API
        ↓
detector / DB / AI / paper / live runtime
~~~

The dashboard does not calculate signals.

It reads backend state and may call authenticated Stage 14/15 control endpoints when the operator supplies the control token.

The control token is stored only in browser sessionStorage for the current tab by the dashboard code.

---

## 15. Runtime

Railway backend start command:

~~~bash
python -m market_radar --serve
~~~

This runs:

- the 5-minute boundary scanner
- HTTP API
- MCP endpoint
- persistence
- AI-approval worker
- position-lifecycle worker
- optional paper loop
- optional guarded live loop

Paper and live loops remain environment-gated.

---

## 16. Authority

For current interface behavior, use:

1. market_radar/read_api.py
2. market_radar/control_state.py
3. market_radar/live_trading.py
4. dashboard/index.html
5. automated tests

This document describes the current interface but does not override source code.
