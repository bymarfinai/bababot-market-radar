# BabaBot Market Radar

Standalone live **Moving Coin Detector (MCD), AI supervision, position lifecycle, paper trading, and guarded live-execution system** for Binance USD-M USDT perpetual markets.

Market Radar has **zero runtime dependency** on bymarfinai/bababot-discovery. Discovery remains the research/backtest lab; validated logic is ported into this repository for production use.

The frozen product contract and production-extension rules are documented in BLUEPRINT.md.

Adaptive Stage 12 profit-protection research is documented in ADAPTIVE_PROFIT_PROTECTION_DISCOVERY.md. That file is the source-of-truth for the frozen 497-trade discovery cohort, Stage 1 reconstruction, and the Stage 2 Giveback Anatomy plan.

## Research / backtest reporting integrity rule

**Never present a detector's META_WIN rate, classification accuracy, or headline win rate by itself as evidence that the strategy is profitable.**

Every research, replay, tuning, detector, gate, and paper-trading result must report the following together whenever the fields exist:

- selected trade count and source-universe trade count
- META_WIN / META_LOSS count and rate, explicitly labeled as **first-touch/path labels**
- realized historical PnL in USD
- average realized return per selected trade (%)
- WIN recall / coverage: selected true WIN divided by all available WIN
- LOSS recall / coverage for a loss detector or veto
- false positives / false vetoes
- discovery / validation / sealed-reserve results separately

Mandatory interpretation rules:

- **META_WIN is not the same as a realized profitable trade.**
- **META_LOSS is not automatically the same as a realized losing trade.**
- MFE >= a threshold is also a different metric from realized return.
- Do not write "WR improved" unless the exact WR definition is stated and realized PnL plus average realized return/trade are shown beside it.
- A high-purity result with tiny coverage must be labeled **low coverage**; never imply that it captures most winners.
- A high-recall result with heavy WIN/LOSS overlap must be labeled **ambiguous capture**, not final classification.
- If META_WIN rate rises while realized PnL is flat, weak, or negative, state that immediately and do not describe the detector as economically successful.
- Paper trading is a validation layer, not permission to accept weak, overfit, misleading, or leakage-contaminated research.
- If a metric is unavailable or has not been computed, say so explicitly instead of substituting another metric.

Canonical caution from the Stage 3 LONG research: a `WIN_ONLY` slice may show a materially higher META_WIN rate while still producing only weak realized economics. Such a result must be reported as **higher META_WIN classification, not proven profitability**, until USD PnL and average realized return/trade are shown.


## Detector research target contract — MFE >= 1%

For the current high-quality WIN-detector research, the target is **META_WIN AND historical maximum favorable excursion (MFE) >= 1.00%**. Both conditions are mandatory. A META_LOSS trade that later rebounds to MFE >= 1.00% is not a target WIN and must remain a non-target for this detector.

Frozen target counts:

- LONG universe: **1,236 resolved LONG trades**
- LONG MFE >= 1.00% targets: **245 trades**
- SHORT universe: **655 resolved SHORT trades**
- SHORT MFE >= 1.00% targets: **99 trades**
- Combined resolved universe: **1,891 trades**
- Combined MFE >= 1.00% targets: **344 trades**

Mandatory reporting for every MFE >= 1% detector result:

- target definition: `primary_meta_label == META_WIN AND historical_max_mfe_pct >= 1.00%`
- exact universe denominator
- exact target count in that universe
- exact number of MFE >= 1% targets captured
- target recall = captured MFE >= 1% / all MFE >= 1% targets
- total trades selected by the detector
- false-positive count = selected trades that do not satisfy BOTH META_WIN and MFE >= 1%
- detector precision for the MFE >= 1% target
- realized historical PnL in USD for selected trades
- average realized return per selected trade (%)
- discovery / validation / sealed-reserve results separately

Non-negotiable interpretation rules:

- Never call META_WIN rate alone the high-quality WIN capture rate; the target requires META_WIN AND MFE >= 1%.
- Never call a high selected-trade win rate a success if MFE >= 1% target recall is low.
- Never quote a percentage without its numerator and denominator when discussing detector quality.
- Never use a smaller favorable subset to imply performance over the full frozen universe.
- Never merge LONG and SHORT denominators unless the result is explicitly labeled combined.
- If a detector captures only a small fraction of the 245 LONG or 99 SHORT MFE >= 1% targets, state that immediately even if precision is high.
- If target recall is high but the detector selects most of the universe, state the false-positive burden immediately.
- Paper trading validates the frozen logic; it does not replace these research checks.

Development placement:

- **Stage 3B — LONG MFE>=1% Capture Detector:** target the 245 MFE>=1% LONG trades inside the 1,236 LONG universe.
- **Stage 5B — SHORT MFE>=1% Capture Detector:** target the 99 MFE>=1% SHORT trades inside the 655 SHORT universe.
- **Stage 6 — Temporal Confirmation:** may improve separation, but must preserve the same MFE>=1% target accounting and may not relabel the target.

Stage 3B frozen result (LONG T0 only):

- 245 high-quality LONG targets = META_WIN AND MFE >= 1% inside 1,236 LONG trades.
- These 245 targets are economically meaningful in the frozen history: realized PnL **+$828.95**, average realized return/trade **+0.677%**.
- T0-only discrimination is weak.
- A validation-tuned ~95% recall operating point captures **36/38 reserve targets (94.7%)** but selects **227/248 reserve trades (91.5%)**.
- A validation-tuned 100% recall operating point captures **38/38 reserve targets** but selects **242/248 reserve trades (97.6%)**.
- Therefore Stage 3B is **FAIL as a practical T0 detector**: high recall can be forced only by selecting almost the entire universe.
- Do not call the forced high-recall result a detector success. Stage 6 temporal confirmation must reduce false positives while preserving the frozen 245-target accounting.


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

Stage 11C populates its start/finish timestamps on every execution-time revalidation.
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

## Stage 11B — Failover-only resilience

Stage 11B is no longer a shadow-voting or escalation layer.

Current version:

~~~text
stage11b-v3-failover-only
~~~

It runs only when the selected Stage 11 fast lane fails.

~~~text
Stage 11 primary lane
    ↓ ERROR
Stage 11B
    ↓
try exactly one alternate fast lane
    ├── success → use APPROVE / WATCH / VETO from that lane
    └── failure → VETO
~~~

Invariants:

- Stage 11B never runs after a successful primary review
- exactly one alternate provider/model may be attempted
- no quorum, majority vote, shadow review, escalation, or tiebreaker
- no direction reversal
- no alternate lane available → VETO
- alternate lane error → VETO
- every failover review is persisted with role `FAST_FAILOVER`

## Stage 11C — Fresh Direction Gate

Stage 11C is the final deterministic revalidation before a new entry order is created.

Current version:

~~~text
stage11c-v2-evidence-families
~~~

V2 no longer treats correlated manifestations of the same price impulse as
independent confirmations. Fresh evidence is normalized into four families:

~~~text
PRICE_STRUCTURE
FLOW
POSITIONING
REGIME
~~~

Family semantics:

- PRICE_STRUCTURE uses fresh closed-1m/3m direction and micro-structure
- FLOW uses fresh closed-1m taker imbalance
- POSITIONING prefers fresh Binance 5m raw open-interest change; signal-time
  positioning is only a fallback when fresh OI cannot be read
- REGIME uses the completed higher-timeframe regime from the original causal
  signal and acts as a modifier, never as the sole reason to enter

The latest 1m return is no longer counted as a second vote on top of 3m
momentum. It is used only to detect impulse concentration / potential
exhaustion.

Flow:

~~~text
Stage 11 APPROVE
    ↓
fresh Binance public data
    ├── ticker price
    ├── closed 1m candles
    └── raw 5m OI history
    ↓
normalize independent evidence families
    ↓
Stage 11C
    ├── ENTER  → create entry order
    ├── WAIT   → no order; retry on a later paper/live cycle
    └── CANCEL → persist skipped entry; do not retry
~~~

Core V2 invariants:

- PRICE_STRUCTURE must be aligned before ENTER
- REGIME cannot qualify an entry by itself
- at least one independent near-entry family from FLOW or POSITIONING must
  support the proposed side
- simultaneous FLOW + POSITIONING opposition cancels
- hard price reversal / opposite micro-structure cancels
- hard chase remains 0.75% by default
- a soft chase zone begins at 0.50%; inside it, both FLOW and POSITIONING must
  independently align before ENTER
- if most of the 3m impulse is concentrated in the latest 1m, both FLOW and
  POSITIONING must independently align before ENTER
- POSITIONING ignores raw OI changes smaller than 0.05% by default
- Stage 11C never changes LONG into SHORT or SHORT into LONG

Every evaluation persists the family map, fresh OI detail, chase flags and
impulse-concentration diagnostics in `entry_revalidations`.

Useful inspection:

~~~text
GET /approval/revalidations
GET /history/cohorts?cohort=POST_ENTRY_REBUILD&fresh_gate_version=stage11c-v2-evidence-families
~~~

Stage 10 records `stage11c_started_at_ms` and
`stage11c_finished_at_ms`. Orders carry the Stage 11C snapshot and must fill
within the configured fill-freshness window.

## Stage 12 — Three-layer position lifecycle

Current version:

~~~text
stage12-v3-three-layer
~~~

Stage 12 V3 separates three different questions that V2 previously blended
inside one health score:

~~~text
OPEN POSITION
    ↓
1. Early Wrong-Direction Guard
    ↓ if safe
2. Profit Protection / MFE Giveback Guard
    ↓ if safe
3. Thesis Health
    ↓
HOLD / REDUCE / CLOSE
~~~

### 1. Early Wrong-Direction Guard

This guard is active only during the early post-entry window (30 minutes by
default). It is designed for positions that never develop meaningful MFE and
start moving against the entry immediately.

Default behavior:

- low-MFE zone: MFE <= 0.35%
- severe MAE: >= 1.00% adverse
- strong current loss: >= 0.60% adverse
- early reduction threshold: >= 0.35% adverse
- normally requires independent fresh contradictions before REDUCE/CLOSE

Fresh contradictions are read from a fast 1m/current-price layer:

- price/micro-structure against the position
- taker flow against the position
- fresh positioning/OI against the position

An invalidated LONG is closed, never reversed into SHORT. A future SHORT still
has to be created independently by Stages 1–11C.

### 2. Profit Protection

Profit protection activates once MFE reaches 0.50% by default.

Default protection:

- MFE >= 1% and giveback >= 55% → REDUCE
- MFE >= 1% and giveback >= 80% → CLOSE
- MFE >= 0.5%, all favorable excursion given back, and fresh contradiction
  present → CLOSE
- smaller armed trades with >= 75% giveback plus contradiction → REDUCE
- a second REDUCE request on an already-reduced position escalates to CLOSE

This is intentionally independent from Thesis Health. A position does not need
to become fundamentally unhealthy before already-earned profit is protected.

### 3. Thesis Health

The existing 5m/15m/1h health model remains the slower thesis layer and still
uses:

- momentum
- structure
- taker flow
- OI interpretation
- higher-timeframe regime
- movement stage
- opposing direction score

V3 uses the market-health score as Thesis Health; MFE/MAE path-memory decisions
are handled by the two guards above rather than requiring health to decay first.

### Fast watcher

The fast guard runs independently from the 5-minute scanner.

~~~text
default poll = 15 seconds
market inputs = current ticker + closed 1m candles + fresh raw 5m OI
AI calls = none
~~~

Only deterministic REDUCE/CLOSE fast observations are persisted. HOLD
observations are not written, so they cannot mask an unexecuted risk-reducing
5m lifecycle action.

The former PP-DECISION V3 Stage 2B.1 5-second shadow observer was retired on 2026-10-03 before the next peak-capture track. Its historical table is preserved for research, but there is no active startup loop, endpoint, or runtime feature flag for that lane. See `research/profit_protection_v3/archive/stage2b1_5s_shadow/ARCHIVE.md`.

The successor research namespace is **PP-DECISION V4 — High-Frequency Peak Capture** (`PP_DECISION_V4.md`). V4 is currently contract-only: no collector loop, endpoint, environment flag, database writer, paper authority, or live authority is active.

The 5-minute Thesis Health path keeps AI supervision as a secondary layer.
A deterministic CLOSE or hard-risk close cannot be upgraded back to HOLD.

## Stage 13 — Event-driven automatic paper trading

Current version:

~~~text
stage13-v2-event-driven
~~~

New entries no longer wait for the paper polling interval after Stage 11 approval.

Normal entry path:

~~~text
Stage 11 final APPROVE
    ↓ immediately
Stage 11C fresh-direction revalidation
    ├── WAIT   → no order; polling loop may retry later
    ├── CANCEL → persist skipped entry
    └── ENTER
          ↓ immediately
       create paper order
          ↓ immediately
       synthetic market fill
~~~

The 10-second paper loop remains as a recovery path for WAIT decisions, deferred
entries, or transient event-handoff failures. Entry handoff and the recovery
loop share the same lock, and the database keeps one unique entry order per
signal, so the same APPROVE cannot be opened twice.

Stage 12 REDUCE/CLOSE lifecycle actions remain poll-driven.

Defaults:

~~~text
notional              = 500 USDT
max open positions    = 5
entry max age         = 15 minutes
reduce fraction       = 50%
fee rate              = 0.075%
slippage              = 2 bps
hard stop             = disabled by default
recovery poll interval = 10 seconds
~~~

Paper trading is controlled by PAPER_TRADING_ENABLED.

### Entry rebuild performance cohorts

Performance after the Stage 6/10/11/11B/11C/13 rebuild is isolated by a
permanent hard boundary:

~~~text
boundary_ms = 1790655250219
PRE_ENTRY_REBUILD  = position opened before boundary
POST_ENTRY_REBUILD = position opened at/after boundary
~~~

The boundary is based on actual `positions.opened_at_ms`, not signal time.

Every opened position is labeled in `pipeline_cohorts`. POST rows freeze the
production stack:

~~~text
stage6-v2-directional-context
stage10-v3-entry-latency
stage11-v3-fast-pool
stage11b-v3-failover-only
stage11c-v1-fresh-direction
stage13-v2-event-driven
~~~

PRE rows are deliberately marked `legacy_or_mixed` rather than assigning a
false historical version.

Use the separated cohort endpoints for performance analysis:

~~~text
GET /history/cohorts
GET /history/cohorts?cohort=POST_ENTRY_REBUILD
GET /history/cohorts/summary
~~~

`GET /paper/summary` also includes `pipeline_cohorts`. Aggregate lifetime
paper totals remain available for audit, but must not be used as the KPI for
the rebuilt entry pipeline.

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
