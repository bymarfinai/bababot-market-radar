# BabaBot Market Radar — Frozen Blueprint + Production Extensions

**Status:** FROZEN CORE + IMPLEMENTED PRODUCTION EXTENSIONS  
**Purpose:** Acuan arsitektur utama BabaBot Market Radar.  
**Rule:** Core detector Stages 1–9 tidak boleh digeser tanpa keputusan eksplisit. Production extensions Stages 10–15 boleh berkembang, tetapi tidak boleh merusak causal detector, runtime independence, auditability, atau fail-closed safety.

---

## 1. Tujuan Utama

BabaBot Market Radar adalah sistem live standalone untuk:

- memantau seluruh Binance USD-M USDT perpetual
- mendeteksi coin yang mulai bergerak
- mengklasifikasikan phase movement
- menilai bukti LONG dan SHORT
- membaca market context
- menghasilkan keputusan deterministic LONG / SHORT / NO TRADE
- menyediakan inspection melalui API/MCP/dashboard
- menyimpan audit trail
- melakukan AI supervision setelah deterministic signal
- mengelola lifecycle posisi
- menjalankan paper trading
- menjalankan guarded live execution hanya ketika seluruh safety gate terpenuhi

Market Radar **bukan** tempat strategy discovery atau backtest.

Research tetap berada di:

~~~text
bymarfinai/bababot-discovery
~~~

Production runtime berada di:

~~~text
bymarfinai/bababot-market-radar
~~~

Runtime dependency Market Radar terhadap Discovery wajib:

~~~text
ZERO
~~~

---

## 2. Frozen Core Plan — Stages 1–9

Core product contract tetap:

1. Scan semua Binance USDT Perpetual tiap ±5 menit
2. Detect coin yang mulai bergerak
3. Classify IGNITION / EXPANSION / EXHAUSTION
4. Calculate LONG_SCORE / SHORT_SCORE
5. Read volume, breakout/breakdown, taker flow, raw OI, funding, market regime
6. Output LONG / SHORT / NO TRADE
7. Expose deterministic radar data through MCP
8. Dashboard live + alert
9. Produce a safe execution handoff

Stage 9 awalnya mendefinisikan **execution integration capability**, bukan live order submission.

Core ini tetap frozen.

---

## 3. Production Extensions — Stages 10–15

Setelah Stages 1–9 selesai, production system diperluas secara eksplisit:

10. Persistent signal/trade database
11. Deterministic risk gate + AI entry approval
11B. Multi-model shadow/escalation/tiebreaker
12. Adaptive position lifecycle
13. Automatic paper trading
14. Persistent trading control plane
15. Guarded Binance Futures live execution

Extensions ini **downstream** dari deterministic Stage 6 decision.

Tidak ada Stage 10–15 yang boleh mengubah candle history, Stage 2 movement facts, Stage 3 labels, Stage 4 scores, atau Stage 5 context secara retroaktif.

---

## 4. Current System Flow

~~~text
Binance USDT Perpetual
        │
        ▼
Stage 1 — closed 5m full-universe scan
        │
        ▼
Stage 2 — Moving Coin Detector
        │
        ▼
Stage 3 — IGNITION / EXPANSION / EXHAUSTION
        │
        ▼
Stage 4 — LONG_SCORE / SHORT_SCORE
        │
        ▼
Stage 5 — market context
        │
        ▼
Stage 6 — LONG / SHORT / NO TRADE
        │
        ├──────────────► Stage 7 MCP/API inspection
        │
        ├──────────────► Stage 8 dashboard/alert
        │
        └──────────────► Stage 9 handoff artifact
        │
        ▼
Stage 10 — persistent actionable signal
        │
        ▼
Stage 11 / 11B — deterministic risk + AI supervision
        │
        ▼
APPROVE / WATCH / VETO
        │
        ├──────────────► VETO/WATCH: no new entry
        │
        ▼
Stage 11C — fresh direction gate
        │
        ├──────────────► WAIT/CANCEL: no new entry
        │
        ▼
Stage 13/15 entry executor
        │
        ▼
OPEN POSITION
        │
        ▼
Stage 12 — HOLD / REDUCE / CLOSE
        │
        ▼
Stage 13 paper or Stage 15 live exit
~~~

Stage 14 control plane sits across entry/exit execution and can block new entries without disabling lifecycle exits.

---

## 5. Moving Coin Detector — Frozen Intent

MCD menjawab:

> Coin mana yang sedang mulai bergerak, ke arah mana tekanan dominannya, dan apakah pergerakan tersebut cukup valid untuk diteruskan ke decision pipeline?

MCD bukan top-gainer scanner.

MCD bukan backtest engine.

MCD bukan strategy discovery engine.

MCD bekerja dari causal live market data.

---

## 6. Stage 1 — Full-Universe Scan

Universe:

~~~text
status       = TRADING
quoteAsset   = USDT
contractType = PERPETUAL
~~~

Wajib:

- scan semua symbol yang eligible
- no top-gainer filter
- no pre-ranking berdasarkan hasil akhir
- use closed candles only
- isolate per-symbol errors
- schedule around closed 5m boundaries

Tujuan Stage 1 adalah observation, bukan decision.

---

## 7. Stage 2 — Early Movement Detection

Fokus utama:

~~~text
noise
normal movement
early movement
strong continuation
late / exhausted movement
~~~

Production baseline menggunakan per-symbol recent history sehingga low-volatility dan high-volatility markets dibandingkan dengan baseline mereka sendiri.

Stage 2 hanya mendeteksi movement facts dan raw direction hint.

Stage 2 tidak menghasilkan LONG/SHORT decision.

---

## 8. Stage 3 — Movement Stage

~~~text
EARLY_MOVEMENT      → IGNITION
STRONG_CONTINUATION → EXPANSION
LATE_MOVEMENT       → EXHAUSTION
~~~

Stage ini menggambarkan phase movement, bukan final trade signal.

EXHAUSTION berarti movement sudah terlalu extended untuk entry baru pada Stage 6.

---

## 9. Stage 4 — Independent Direction Scores

Setiap candidate memiliki:

~~~text
LONG_SCORE
SHORT_SCORE
score_gap
score_edge
~~~

LONG dan SHORT bukan simple mirror.

Stage 4 menilai evidence dari movement/momentum/activity yang sudah tersedia.

Stage 4 tidak boleh membaca Stage 5 context untuk mengubah score setelah fakta.

---

## 10. Stage 5 — Market Context

Context wajib mencakup:

### Volume
- current closed-5m volume
- relative expansion
- confirmation flag

### Structure
- breakout
- breakdown
- failed breakout
- failed breakdown
- no structural break

### Taker Flow
- aggressive taker buy/sell pressure
- same closed candle alignment

### Raw Open Interest
Gunakan:

~~~text
sumOpenInterest
~~~

Jangan mengganti dasar dengan:

~~~text
sumOpenInterestValue
~~~

Interpretasi:

~~~text
Price ↑ + OI ↑ → fresh long participation
Price ↑ + OI ↓ → short covering
Price ↓ + OI ↑ → fresh short participation
Price ↓ + OI ↓ → long liquidation
~~~

### Funding
Funding hanya context.

Funding tidak boleh berdiri sendiri sebagai trigger LONG/SHORT.

### Market Regime
Existing validated regime logic boleh di-port ke repo ini.

Market Radar tidak boleh memanggil Discovery at runtime untuk regime.

---

## 11. Stage 6 — Final Deterministic Decision

Output final:

~~~text
LONG
SHORT
NO TRADE
~~~

NO TRADE adalah keputusan valid.

Core invariants:

- incomplete required context fails closed
- EXHAUSTION cannot become a new trade
- hard structure contradiction blocks the proposed side
- score and score-edge gates must pass
- activity evidence such as volume expansion cannot qualify LONG/SHORT by itself
- every LONG/SHORT requires at least one core directional confirmation from structure, taker flow, or fresh OI
- market regime may reinforce direction but cannot be the sole entry proof
- IGNITION requires at least two total directional confirmations
- EXPANSION requires at least one total directional confirmation
- directional confirmation must outweigh conflict
- reasons must be inspectable

Current decision version: `stage6-v2-directional-context`.

Stage 6 remains deterministic.

AI does not own Stage 6.

---

## 12. Stage 7 — MCP

MCP adalah read-only inspection interface.

MCP boleh:

- read current radar
- filter moving candidates
- inspect a symbol

MCP tidak boleh:

- rescan Binance
- recalculate detector
- rewrite scores
- change final decision
- execute orders
- mutate trading control

Current MCP tools remain exactly:

~~~text
get_market_radar
get_moving_coins
inspect_symbol
~~~

---

## 13. Stage 8 — Dashboard / Trading Control Center

Dashboard bertugas memvisualisasikan current system state.

Current scope mencakup:

- radar
- candlestick chart
- movement stage
- direction scores
- context
- deterministic decision
- AI approval
- per-model reviews
- open-position health
- paper orders
- signal history
- control state
- live preflight
- live arm/disarm

Frontend boleh dipisahkan dari engine.

Frontend tidak menjadi calculation authority.

---

## 14. Stage 9 — Safe Execution Handoff

Stage 9 tetap dipertahankan sebagai deterministic handoff artifact:

~~~text
data/execution_intents.json
GET /execution/intents
~~~

Only:

~~~text
LONG
SHORT
~~~

Never:

~~~text
NO TRADE
~~~

Stage 9 artifact tetap HANDOFF_ONLY dan non-executable.

Ini adalah historical integration contract dan audit surface.

Field live_order_submission_enabled=false di artifact Stage 9 **hanya berarti artifact tersebut sendiri tidak mengeksekusi order**.

Field itu tidak lagi berarti repository tidak memiliki live execution path, karena Stage 15 sekarang ada sebagai downstream production extension.

---

## 15. Stage 10 — Persistence

Actionable signals dan downstream actions wajib auditable.

Production persistence:

~~~text
PostgreSQL primary
SQLite safety/fallback ledger
~~~

Persisted state dapat mencakup:

- signals
- outcomes
- AI approvals
- model reviews
- positions
- position evaluations
- paper/live orders
- control state
- trade events

Signal identity wajib deterministic dan idempotent.

---

## 16. Stage 11 / 11B — AI Supervision

AI berada **setelah** deterministic Stage 6 signal.

Mandatory sequence:

~~~text
Stage 6 signal
    ↓
deterministic fail-closed risk gate
    ↓
priority queue (freshest / strongest first)
    ↓
one fast AI lane
    ├── Clario: gemini-3.7-flash
    └── Thirty: thirty/gpt-5.6-luna
    ↓
APPROVE / WATCH / VETO
~~~

Stage 11 V3 invariants:

- one signal receives one normal-path AI review, not per-signal shadow voting
- signals are distributed across independent provider lanes concurrently
- each provider owns an independent rate-limit lock
- a primary provider error may route once to the other fast lane
- if both fast lanes fail, the signal fails closed
- cannot reverse LONG into SHORT
- cannot reverse SHORT into LONG
- cannot invent missing market data
- cannot bypass deterministic safety failure
- WATCH does not permit entry
- only final APPROVE may feed an entry executor

Stage 11B is a failover-only resilience layer:

- it activates only after the selected Stage 11 lane errors
- it may attempt exactly one alternate fast lane
- successful alternate verdict becomes the Stage 11 verdict
- alternate failure or absence fails closed to VETO
- shadow voting, escalation, quorum, and tiebreaker paths are forbidden


Stage 11C is the final deterministic execution-time direction gate.

Stage 11C V2 invariants:

- current version is `stage11c-v2-evidence-families`
- runs only after final Stage 11 APPROVE
- reads fresh public market data at execution time
- output is ENTER, WAIT, or CANCEL
- never reverses the Stage 6/11 direction
- correlated observations must be normalized into PRICE_STRUCTURE, FLOW,
  POSITIONING, and REGIME families
- 1m and 3m momentum cannot be counted as two independent votes
- REGIME is a modifier and cannot qualify an entry by itself
- ENTER requires aligned PRICE_STRUCTURE plus independent near-entry support
  from FLOW or POSITIONING
- raw OI changes below the configured floor are neutral, not confirmation
- soft chase / concentrated impulse requires both FLOW and POSITIONING to align
- stale signal/approval or hard excessive price chase may CANCEL
- hard fresh contradiction may CANCEL
- mixed/insufficient fresh evidence returns WAIT
- only ENTER may create a new entry order
- Stage 11C verdict, family map, reasons, and snapshot must be persisted
- an ENTER verdict has a short fill-freshness TTL; stale gate results cannot fill

---

## 17. Stage 12 — Position Lifecycle

Current version: `stage12-v3-three-layer`.

For already-open positions, entry validation and lifecycle management remain
separate. Stage 12 V3 has three ordered deterministic layers:

~~~text
Early Wrong-Direction Guard
        ↓
Profit Protection / Giveback Guard
        ↓
Thesis Health
        ↓
HOLD / REDUCE / CLOSE
~~~

Invariants:

- early invalidation is allowed to close a position before the slower health
  score collapses when MFE stays small and fresh independent evidence turns
  against the entry
- profit protection is allowed to REDUCE/CLOSE after meaningful MFE when a
  large fraction of that favorable excursion is given back
- Thesis Health remains the slower 5m/15m/1h market-thesis layer
- fast guards use current price, closed 1m context, taker flow and fresh raw OI
- fast guards are deterministic and do not call AI
- AI position supervision remains secondary to the 5m Thesis Health path
- deterministic CLOSE and hard-risk CLOSE cannot be overridden
- Stage 12 may close an invalid LONG/SHORT but may never reverse it into the
  opposite side
- a new opposite position still requires a new independent Stage 6 → 11C path
- risk-reducing exits remain available in PAUSE_ENTRIES and EXIT_ONLY

Deterministic actions remain:

~~~text
HOLD
REDUCE
CLOSE
~~~

## 18. Stage 13 — Paper Trading

Paper execution is the mandatory observation/testing bridge before guarded live execution.

Paper trading must:

- use actual live signal timing
- model adverse slippage
- include fees
- prevent duplicate same-signal entries
- limit open positions
- consume Stage 11 APPROVE
- require Stage 11C ENTER before opening
- immediately hand off fresh APPROVE → 11C → order → fill without waiting for poll cadence
- keep polling only as recovery for WAIT/deferred/transient handoff failures
- serialize event-driven and polling entry execution through one entry lock
- consume Stage 12 REDUCE/CLOSE
- persist fills and PnL

Current paper execution version is `stage13-v2-event-driven`.

Paper performance may be used as a live-entry gate.

Performance evaluation of the rebuilt entry pipeline must use a hard cohort
boundary based on actual position open time:

~~~text
boundary_ms = 1790655250219
PRE_ENTRY_REBUILD  = opened_at_ms < boundary
POST_ENTRY_REBUILD = opened_at_ms >= boundary
~~~

PRE and POST must never be blended when evaluating whether the rebuilt entry
pipeline improved win rate, PnL, MFE/MAE, immediate wrong-direction rate, or
entry latency. Historical PRE data remains available only as a comparison
baseline.

Paper trading is not historical backtesting.

---

## 19. Stage 14 — Control Plane

Persistent control modes:

~~~text
RUN
PAUSE_ENTRIES
EXIT_ONLY
~~~

Invariant:

> Blocking new entries must never unintentionally disable legitimate risk-reducing exits.

RUN:
- entries allowed if all other gates pass
- exits allowed

PAUSE_ENTRIES:
- no new entries
- exits allowed

EXIT_ONLY:
- no new entries
- REDUCE/CLOSE allowed

Control mutation must require authentication.

---

## 20. Stage 15 — Guarded Live Execution

Live execution exists, but must remain explicitly gated and fail-closed.

A live entry requires:

- live environment enabled
- credentials configured
- persistent ARM state true
- RUN mode
- approved fresh signal
- bounded notional
- bounded leverage
- paper gate
- daily-loss gate
- loss-streak gate
- position-capacity gate
- exchange account tradable
- supported one-way position mode
- sufficient balance
- no unmanaged exchange position
- acceptable spread
- no duplicate live symbol position

Risk invariants:

1. Exit processing has priority over new entries.
2. ARM controls new entry eligibility, not the ability to exit.
3. PAUSE_ENTRIES / EXIT_ONLY must not block REDUCE/CLOSE.
4. Every new live position must receive exchange-side protection.
5. If protective-stop placement fails, immediate emergency close is attempted.
6. If protection and emergency close both fail, the condition must be surfaced as critical.
7. Live reconciliation must detect exchange positions that no longer match persisted state.

---

## 21. Runtime Independence — Wajib

Architecture yang dilarang:

~~~text
Market Radar
    ↓ runtime call
BabaBot Discovery
    ↓
ambil regime / score / signal
~~~

Architecture yang benar:

~~~text
BabaBot Discovery
= LAB
= research
= backtest
= experimentation
= validation

        ↓ validated logic

BabaBot Market Radar
= LIVE PRODUCT
= STANDALONE RUNTIME
= deterministic detector
= supervision
= execution controls
~~~

Discovery dapat menemukan improvement.

Improvement harus divalidasi dahulu.

Hanya validated/approved logic yang dipindahkan ke Market Radar.

---

## 22. Deployment Direction

Current intended separation:

~~~text
GitHub
│
├── bababot-discovery
│      └── research/backtest deployment as needed
│
├── bababot-market-radar
│      └── Railway
│          ├── scanner
│          ├── persistence
│          ├── MCP/API
│          ├── AI supervision
│          ├── position lifecycle
│          ├── paper engine
│          └── guarded live engine
│
└── dashboard/
       └── Vercel static frontend
~~~

Calculation authority stays in Market Radar backend.

---

## 23. Non-Scope / Forbidden Drift

Market Radar must not become:

~~~text
❌ historical backtest engine
❌ parameter optimizer
❌ generic strategy discovery lab
❌ runtime proxy to BabaBot Discovery
❌ ML training environment
❌ non-causal scanner using future candles
❌ AI-first signal generator that bypasses deterministic stages
❌ uncontrolled auto-trading engine
❌ dashboard-owned calculation engine
~~~

---

## 24. Current Definition

BabaBot Market Radar adalah:

> Standalone live production system yang melakukan causal closed-candle scan terhadap seluruh Binance USDT perpetual, mendeteksi abnormal early movement melalui Moving Coin Detector, mengklasifikasikan IGNITION / EXPANSION / EXHAUSTION, menghitung independent LONG_SCORE / SHORT_SCORE, membaca volume/structure/taker/raw OI/funding/regime, menghasilkan deterministic LONG / SHORT / NO TRADE, menyediakan MCP/API/dashboard inspection, menyimpan audit trail, menerapkan deterministic + AI supervision, mengelola position lifecycle, menjalankan paper trading, dan hanya mengizinkan guarded live execution apabila seluruh persistent control dan safety gate terpenuhi.

---

## 25. Current Checklist

### Frozen core
- [x] Full USDT perpetual scan
- [x] Early movement detector
- [x] IGNITION / EXPANSION / EXHAUSTION
- [x] LONG_SCORE / SHORT_SCORE
- [x] Volume context
- [x] Structure context
- [x] Taker flow
- [x] Raw Open Interest
- [x] Funding
- [x] Existing market regime port
- [x] LONG / SHORT / NO TRADE
- [x] MCP inspection
- [x] Dashboard
- [x] Alert
- [x] Execution handoff

### Production extensions
- [x] PostgreSQL/SQLite persistence
- [x] Deterministic AI pre-risk gate
- [x] AI entry approval
- [x] Multi-model supervision
- [x] Position health lifecycle
- [x] Paper execution
- [x] Persistent control plane
- [x] Guarded Binance Futures execution
- [x] Protective stop + emergency-close path
- [x] Live reconciliation
- [x] Dashboard live arm/preflight controls

### Architectural invariants
- [x] No runtime dependency on bababot-discovery
- [x] No historical strategy discovery inside Market Radar
- [x] Closed-candle causal detector
- [x] AI cannot reverse deterministic trade direction
- [x] Live entries fail closed
- [x] Risk-reducing exits remain available independently of live ARM
- [x] Source + tests remain final authority for exact implementation details

---

**This document is the frozen architectural baseline plus the approved production extensions currently implemented through Stage 15.**
