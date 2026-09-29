# BabaBot Market Radar

Standalone live **Moving Coin Detector (MCD), AI supervision, position lifecycle, paper trading, and guarded live-execution system** for Binance USD-M USDT perpetual markets.

Market Radar has **zero runtime dependency** on bymarfinai/bababot-discovery. Discovery remains the research/backtest lab; validated logic is ported into this repository for production use.

The frozen product contract and production-extension rules are documented in BLUEPRINT.md.

## Current development state

**Stages 1–15 are implemented.**

The original frozen product plan covered Stages 1–9. Stages 10–15 are production extensions added after the core radar was completed.

| Stage | Status | Responsibility |
|---|---|---|
| 1 | COMPLETE | Full Binance USDT perpetual scan |
| 2 | COMPLETE | Moving Coin Detector |
| 3 | COMPLETE | IGNITION / EXPANSION / EXHAUSTION |
| 4 | COMPLETE | Independent LONG_SCORE / SHORT_SCORE |
| 5 | COMPLETE | Market context |
| 6 | COMPLETE | LONG / SHORT / NO TRADE |
| 7 | COMPLETE | Read-only MCP + radar API |
| 8 | COMPLETE | Dashboard + actionable alerts |
| 9 | COMPLETE | Safe execution handoff contract |
| 10 | COMPLETE | PostgreSQL/SQLite persistence |
| 11 | COMPLETE | Deterministic entry risk gate + AI approval |
| 11B | COMPLETE | Multi-model shadow/escalation/tiebreak |
| 12 | COMPLETE | Adaptive position lifecycle |
| 13 | COMPLETE | Automatic paper trading |
| 14 | COMPLETE | Trading Control Center |
| 15 | COMPLETE | Guarded Binance Futures live execution |

## Current production flow

~~~text
Binance USDT Perpetual
        ↓
Stage 1 — full-universe closed-5m scan
        ↓
Stage 2 — Moving Coin Detector
        ↓
Stage 3 — IGNITION / EXPANSION / EXHAUSTION
        ↓
Stage 4 — LONG_SCORE / SHORT_SCORE
        ↓
Stage 5 — market context
        ↓
Stage 6 — LONG / SHORT / NO TRADE
        ↓
Stage 10 — persistent actionable signal ledger
        ↓
Stage 11 / 11B — deterministic risk gate + AI supervision
        ↓
APPROVE / WATCH / VETO
        ↓
Stage 12 — position health + HOLD / REDUCE / CLOSE
        ↓
Stage 13 — paper execution
        ↓
Stage 14 — RUN / PAUSE_ENTRIES / EXIT_ONLY control plane
        ↓
Stage 15 — guarded live Binance Futures execution
~~~

MCP and dashboard inspection run alongside this pipeline. They do not replace the deterministic detector.

## Stage 1 — Full-universe scanner

Market Radar discovers every currently trading Binance USD-M contract matching:

~~~text
quoteAsset   = USDT
contractType = PERPETUAL
status       = TRADING
~~~

There is **no top-gainer, momentum, volume, or liquidity pre-filter**.

The scheduler runs on each UTC 5-minute candle boundary plus a small close-confirmation offset. Only fully closed candles are admitted.

## Stage 2 — Moving Coin Detector

The MCD compares each symbol with its own previous 20 closed 5m bars.

Default production thresholds:

~~~text
minimum absolute 5m return       = 0.15%
return expansion                 = 2.0x baseline
volume expansion                 = 1.5x baseline
range expansion                  = 1.4x baseline
trade-count expansion            = 1.5x baseline

strong return expansion          = 3.0x
strong volume expansion          = 2.0x
strong range expansion           = 1.6x

late same-direction 1h move      = 6%
late same-direction 24h move     = 30%
~~~

A symbol becomes a moving candidate only when:

~~~text
abs(5m return) >= 0.15%
AND return expansion >= 2.0x
AND at least one activity confirmation:
    volume expansion
    OR range expansion
    OR trade-count expansion
~~~

Movement states:

~~~text
NOISE
NORMAL
EARLY_MOVEMENT
STRONG_CONTINUATION
LATE_MOVEMENT
~~~

The detector is intentionally built for **abnormal early movement detection**, not for chasing the final top-gainer list.

## Stage 3 — Movement stage

Deterministic mapping:

~~~text
EARLY_MOVEMENT      → IGNITION
STRONG_CONTINUATION → EXPANSION
LATE_MOVEMENT       → EXHAUSTION
~~~

NOISE and NORMAL remain outside the actionable movement-stage pipeline.

## Stage 4 — Direction scoring

Every moving candidate receives independent 0–100 evidence scores:

~~~text
LONG_SCORE
SHORT_SCORE
score_gap  = LONG_SCORE - SHORT_SCORE
score_edge = abs(score_gap)
~~~

The scores are not complements and are not required to sum to 100.

Stage 4 uses signed 5m/15m/1h momentum, short-term acceleration, activity expansion, directional persistence, and timeframe consistency.

Stage 4 does **not** use Stage 5 market context and does **not** issue the final trade decision.

## Stage 5 — Market context

Context is attached only after Stage 2 confirms a moving candidate.

Current context:

- relative volume confirmation
- previous 20 closed-5m high/low
- BREAKOUT / BREAKDOWN
- FAILED_BREAKOUT / FAILED_BREAKDOWN / FAILED_BOTH_SIDES
- taker BUY / SELL / BALANCED bias from the same closed Binance kline
- raw Binance Open Interest using sumOpenInterest only
- funding rate
- causal completed-4H market regime

Raw OI interpretation:

~~~text
Price ↑ + OI ↑ → FRESH_LONG_PARTICIPATION
Price ↑ + OI ↓ → SHORT_COVERING
Price ↓ + OI ↑ → FRESH_SHORT_PARTICIPATION
Price ↓ + OI ↓ → LONG_LIQUIDATION
~~~

The regime implementation is the existing BabaBot B27AG swing-regime logic ported into this repo:

~~~text
BULL:
HH >= 2
HL >= 2
EMA7 > EMA20
completed close > EMA20

BEAR:
LH >= 2
LL >= 2
EMA7 < EMA20
completed close < EMA20

otherwise SIDEWAYS
~~~

Only completed 4H candles are used.

## Stage 6 — Final deterministic decision

Output:

~~~text
LONG
SHORT
NO TRADE
~~~

Default score gates:

~~~text
winning score >= 68
score edge    >= 10
~~~

Additional rules:

- EXHAUSTION is always NO TRADE
- required OI, funding, and regime context must be available
- a confirmed structural break directly against the proposed side is a hard conflict
- volume expansion is **activity evidence only** and does not count as directional confirmation
- core directional confirmations are structure alignment, taker-flow alignment, and fresh-OI alignment
- market regime can reinforce the proposed side but cannot qualify an entry by itself
- every LONG/SHORT requires at least 1 core directional confirmation
- IGNITION requires at least 2 total directional confirmations
- EXPANSION requires at least 1 total directional confirmation
- directional confirmation-minus-conflict balance must be at least +1
- funding is observational context and is not a standalone trigger or veto

Every rejected setup receives explicit decision reasons. Stage 6 decision version is
`stage6-v2-directional-context`.

## Stage 7 — MCP and read API

MCP remains **read-only** and exposes exactly three tools:

~~~text
get_market_radar
get_moving_coins
inspect_symbol
~~~

Endpoint:

~~~text
POST /mcp
~~~

Protocol revision:

~~~text
2025-11-25
~~~

Production radar/API service:

~~~text
https://market-radar-production-d307.up.railway.app
~~~

See MCP_ADAPTER.md for the current interface contract.

## Stage 8 — Dashboard

The dashboard is now the **BabaBot Trading Control Center**, not only a read-only radar page.

It includes:

- current radar and candidate filters
- selected-symbol candlestick chart
- scores, stage, structure, taker, OI, funding, and regime
- AI approval status and per-model reviews
- open-position health and lifecycle actions
- paper-order and signal history
- control modes
- Stage 15 live preflight state
- ARM LIVE / DISARM LIVE controls

The current browser refresh interval is **10 seconds**.

The static dashboard lives in dashboard/ and is configured for **Vercel static deployment** through dashboard/vercel.json. The calculation engine and authenticated trading runtime remain on Railway.

The dashboard stores the control token only in browser sessionStorage for the active tab.

## Stage 9 — Historical execution handoff contract

Stage 9 still writes the safe historical handoff:

~~~text
data/execution_intents.json
GET /execution/intents
~~~

Only Stage 6 LONG / SHORT decisions become intents. NO TRADE never becomes an intent.

Each Stage 9 intent remains:

~~~text
execution_mode     = HANDOFF_ONLY
risk_confirmation  = PENDING
execution_status   = BLOCKED
executable         = false
entry_price        = null
quantity           = null
stop_loss          = null
take_profit        = null
~~~

Important: the Stage 9 field live_order_submission_enabled=false describes **the Stage 9 handoff artifact only**. It does not describe the current Stage 15 guarded live engine.

See EXECUTION_HANDOFF.md.

## Stage 10 — Persistence

Primary production persistence uses PostgreSQL when DATABASE_URL is configured.

SQLite at BABABOT_DB_PATH remains a local/fallback safety ledger.

Current persistent data includes:

~~~text
signals
signal_outcomes
ai_reviews
entry_approvals
ai_model_reviews
positions
position_evaluations
trade_events
entry_latency
persistence_meta
paper_orders
live_orders
control_state
live_activation_state
~~~

Actionable signal identity is deterministic:

~~~text
symbol + candle_close_time_ms + side
~~~

Stage 10 V3 also records end-to-end entry timing in `entry_latency`:

~~~text
candle_close_at_ms
scan_started_at_ms
scan_finished_at_ms
signal_created_at_ms
ai_queued_at_ms
ai_started_at_ms
ai_finished_at_ms
stage11c_started_at_ms
stage11c_finished_at_ms
order_created_at_ms
position_opened_at_ms
~~~

Stage 11C timestamps are reserved and remain null until that stage is implemented.
The read-only endpoint `GET /history/entry-latency` returns the raw timestamps plus derived segments such as scan duration, AI queue wait, AI review time, order-to-fill time, signal-to-fill, and candle-to-fill.

## Stage 11 — Entry risk gate and fast AI pool

Only deterministic Stage 6 LONG / SHORT signals reach Stage 11.

Before an AI model is called, a fail-closed deterministic risk gate verifies:

- side is LONG or SHORT
- stage is IGNITION or EXPANSION
- winning score >= 68
- score edge >= 10
- context balance >= 1
- signal price exists
- required market context exists
- no hard structural conflict
- signal is not stale

Current approval version:

~~~text
stage11-v3-fast-pool
~~~

Normal path is now one review per signal, not shadow voting.

~~~text
fresh/strong actionable signals
        ↓
priority queue
        ↓
┌───────────────────────────────┬────────────────────────────────┐
│ Clario                        │ Thirty                         │
│ gemini-3.7-flash              │ thirty/gpt-5.6-luna           │
└───────────────────────────────┴────────────────────────────────┘
        ↓
APPROVE / WATCH / VETO
~~~

Signals are distributed round-robin across the two fast lanes and processed
concurrently. Each provider has its own rate-limit lock, so a slow Clario call
does not serialize Thirty and vice versa.

Pending signals are prioritized by:

1. newest signal time
2. winning direction score
3. score edge
4. directional context balance

A successful primary lane verdict is final for Stage 11. No shadow model is
called on the normal path. If that lane errors, the signal is routed once to
the other fast lane. If both lanes fail, the signal fails closed to VETO.

The AI supervisor may return:

~~~text
APPROVE
WATCH
VETO
~~~

It may **not reverse direction**. A LONG signal cannot become SHORT and a SHORT
signal cannot become LONG.

## Stage 11B — Legacy multi-model module / rollback path

The Stage 11B shadow/escalation/tiebreak code remains in the repository for
rollback compatibility, but **it is no longer part of the Stage 11 normal
entry path**. The current production direction is fast provider failover rather
than per-signal multi-model voting.

## Stage 12 — Position lifecycle

Every open/reduced position is evaluated against fresh closed-candle market context.

The deterministic Position Health Engine is the primary controller and emits:

~~~text
HOLD
REDUCE
CLOSE
~~~

### Health V2 — adaptive position health

Current lifecycle version:

~~~text
stage12-v2-adaptive-health
~~~

Health V2 keeps the original live market-context score as **Base Health**:

~~~text
Base Health =
    momentum
  + structure
  + taker flow
  + OI interpretation
  + market regime
  + movement stage
~~~

The live context is rebuilt on every lifecycle evaluation from fresh closed candles. OI, taker, structure, regime, momentum, and movement stage are therefore **not frozen at entry**.

Current maximum Base Health remains 100:

~~~text
momentum   30
structure  20
taker      15
OI         15
regime     10
stage      10
~~~

Health V2 adds trade-path memory without replacing current market context:

~~~text
Adaptive Health =
    Base Health
  - MAE penalty
  - MFE giveback penalty
~~~

Current adaptive rules:

~~~text
MAE penalty activates only when:
current unrealized PnL <= 0
AND Base Health < 60

MAE <= -1.0%  → -8
MAE <= -1.5%  → -15

No historical MAE penalty is applied after the position has recovered above entry.

MFE giveback protection activates only when:
MFE >= +1.0%
AND Base Health < 70

giveback >= 50% of MFE → -10
giveback >= 75% of MFE → -20
~~~

Where:

~~~text
giveback       = MFE - current unrealized PnL
giveback ratio = giveback / MFE
~~~

The purpose is **not** to turn Health into a fixed take-profit or stop-loss system. Health still answers one lifecycle question:

> Given the market condition now and the path of this already-open trade since entry, should the position be HOLD, REDUCE, or CLOSE?

A strong current Base Health is deliberately allowed to keep a profitable position running even after a normal retracement.

### Health V2 validation before deployment

Health V2 was derived from the first 105 completed paper positions.

Observed baseline sample:

~~~text
closed positions              105
final wins                     37
final losses                   68
average MFE — final wins      +2.743%
average MFE — final losses    +0.740%
average MAE — final wins      -0.370%
average MAE — final losses    -1.163%

positions reaching MFE >= 1%   49
of those ending as loss         20
~~~

At the first +1% MFE observation, those 20 eventual losses still had average Health about 74.75 and 17/20 were still HOLD. This was the main reason to add trade-path memory.

The first aggressive adaptive formula was rejected because it changed too many historical actions. The deployed V2 is the tighter **minimal-soft** variant: MAE only matters while the trade remains unrecovered and weak, while MFE protection only activates after >=1% favorable excursion plus substantial giveback and weakening Base Health.

A rough historical replay of the deployed candidate improved relative simulated capture versus the old lifecycle, but that replay is **not treated as a profitability backtest** because it is counterfactual and does not fully reproduce fees, slippage, and changed execution paths.

### Health V2 — deliberately NOT added yet

The following moving Stage 5/context features are already collected or derivable but are **not yet additional adaptive Health factors**. They are intentionally deferred until Health V2 has a fresh paper-trading cohort, so their incremental effect can be measured cleanly:

- **funding rate** — collected in the lifecycle snapshot, currently not scored in Health
- **raw OI change magnitude** — Health currently uses categorical OI interpretation, not the numerical size of the OI move
- **OI trajectory across lifecycle evaluations** — no OI rising/falling acceleration or change-from-previous-health memory yet
- **taker-flow trajectory** — Health uses the current BUY / SELL / BALANCED bias, not persistence or change in taker buy share over multiple evaluations
- **structure transition memory** — current structure is scored, but transitions such as BREAKOUT → NO_STRUCTURAL_BREAK → FAILED_BREAKOUT are not separately weighted
- **regime transition memory** — current 4H BULL / BEAR / SIDEWAYS is scored, but regime deterioration across evaluations is not separately weighted

These are **candidate refinements, not planned additions by default**. The next validation step is to run Health V2 unchanged on a fresh executable paper cohort first, then inspect the remaining bad HOLD/REDUCE/CLOSE cases to determine whether any of these dynamic context changes provide real incremental information.

AI position review maps:

~~~text
APPROVE → HOLD
WATCH   → REDUCE
VETO    → CLOSE
~~~

AI receives the deterministic Health object, including the adaptive Health components. AI cannot override a deterministic CLOSE or hard-risk CLOSE.

## Stage 13 — Automatic paper trading

Paper execution uses Stage 11 final APPROVE entries and Stage 12 REDUCE/CLOSE actions.

Defaults:

~~~text
notional              = 500 USDT
max open positions    = 5
entry max age         = 15 minutes
reduce fraction       = 50%
fee rate              = 0.075%
slippage              = 2 bps
hard stop             = disabled by default
poll interval          = 10 seconds
~~~

Paper trading is controlled by PAPER_TRADING_ENABLED.

## Stage 14 — Trading Control Center

Persistent control modes:

~~~text
RUN
PAUSE_ENTRIES
EXIT_ONLY
~~~

Semantics:

- RUN permits new eligible paper entries and, when Stage 15 is fully armed, live entries
- PAUSE_ENTRIES blocks new entries while lifecycle exits remain enabled
- EXIT_ONLY blocks new entries while REDUCE/CLOSE remain enabled

Authenticated state changes require CONTROL_API_TOKEN through X-Baba-Control-Token.

Control endpoints:

~~~text
GET  /control/state
POST /control/state
POST /control/live-arm
~~~

## Stage 15 — Guarded live Binance Futures execution

Live execution is **fail-closed** and requires multiple independent guards.

Current bounded defaults:

~~~text
live notional                  = 25 USDT
hard notional cap              = 50 USDT
max open live positions        = 1
leverage                       = 1x
maximum Stage 15 leverage      = 3x
hard protective stop           = 1.5%
daily loss limit               = 10 USDT
maximum recent loss streak     = 3
minimum closed paper trades    = 20
paper net PnL requirement      = >= 0
entry max age                  = 10 minutes
reduce fraction                = 50%
maximum spread                 = 20 bps
balance buffer                 = 1.25x
live poll interval             = 10 seconds
~~~

A new live entry requires all of the following:

- LIVE_TRADING_ENABLED=true
- Binance API credentials configured
- persistent live ARM state = true
- control mode = RUN
- configured notional within the hard cap
- paper gate passed
- daily loss limit not reached
- loss-streak limit not reached
- live-position capacity available
- Binance account can trade
- one-way position mode; hedge mode is rejected
- sufficient available USDT
- no unmanaged Binance position
- no existing live position for the same symbol
- spread within the configured cap
- fresh Stage 11 APPROVE

Live entries use isolated margin and bounded leverage.

Immediately after a live market entry, Stage 15 submits an exchange-side protective stop. If the protective stop cannot be created, the engine attempts an emergency reduce-only market close. A failure of both protection and emergency close is marked CRITICAL_UNPROTECTED.

Lifecycle exits are deliberately safer than entries:

- exit orders are processed before new entries
- live ARM is not required for exits
- RUN mode is not required for exits
- live exits remain available when live environment and credentials are configured

Read endpoints:

~~~text
GET /live/preflight
GET /live/summary
GET /live/orders
GET /live/positions
~~~

## API overview

Read/inspection:

~~~text
GET /health
GET /radar/latest
GET /radar/candidates
GET /radar/symbol/{symbol}
GET /market/klines
GET /execution/intents
GET /history/summary
GET /history/signals
GET /approval/summary
GET /approval/reviews
GET /approval/models
GET /approval/models/summary
GET /positions/open
GET /positions/evaluations
GET /paper/summary
GET /paper/orders
GET /live/preflight
GET /live/summary
GET /live/orders
GET /live/positions
GET /control/state
~~~

Authenticated control:

~~~text
POST /control/state
POST /control/live-arm
~~~

MCP:

~~~text
POST /mcp
~~~

## Runtime

Install:

~~~bash
python -m pip install -r requirements.txt
~~~

Run one scan:

~~~bash
python -m market_radar --once
~~~

Machine-readable one-shot scan:

~~~bash
python -m market_radar --once --json
~~~

Continuous scanner:

~~~bash
python -m market_radar
~~~

Continuous scanner + HTTP/MCP/control API:

~~~bash
python -m market_radar --serve
~~~

## Tests

~~~bash
python -m unittest discover -s tests -v
~~~

## Repository boundary

bymarfinai/bababot-discovery remains responsible for:

~~~text
backtest
historical research
strategy discovery
parameter exploration
validation
experimentation
~~~

bymarfinai/bababot-market-radar remains responsible for:

~~~text
live detection
production scoring
market context
deterministic decisions
AI supervision
position lifecycle
paper execution
guarded live execution
control plane
dashboard/API/MCP
persistent audit trail
~~~

Do not add historical strategy discovery or parameter optimization into this runtime.

## Documentation authority

For current behavior, use this order of authority:

1. production source code
2. automated tests
3. current README / supporting MD contracts
4. historical commit messages

BLUEPRINT.md remains the architectural contract; source code is the final authority for exact implemented defaults.
