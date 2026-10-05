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


## Stage 3C strong-parameter discovery status

Frozen LONG target remains **245 / 1,236** trades satisfying BOTH `META_WIN` and historical MFE >= 1.00%.

### Stage 3C.1 — exhaustive single-parameter tuning

Stage 3C.1 explicitly tests the concern that a weak raw correlation may hide a nonlinear sweet spot such as volume 2.5–3.0x or OI inside a narrow band.

The frozen T0 set contains **224 parameters** after excluding seven time / infrastructure-latency fields:

- 210 numeric
- 14 categorical

Every numeric feature is tuned independently using exact Discovery-observed boundaries for:

- `x <= threshold`
- `x >= threshold`
- contiguous `low <= x <= high` bands

Categorical states are also tested. Candidate generation occurs on Discovery; per-feature thresholds are selected for positive stability across Discovery + Validation; the rule is then frozen before sealed Reserve evaluation.

Total search size:

- **32,275,307 numeric candidate rules**
- **72 categorical candidate rules**
- **32,275,379 total candidate rules**

Result: **NO STRONG SINGLE-PARAMETER RULE FOUND.**

Important examples:

- best Discovery-only pocket: `f_f_market_dispersion_15m`, r ≈ **0.214**, but it collapses in Validation
- tuned `f_f_coin_minus_market_30m` band ≈ **2.919–4.426** gives r ≈ **0.110 / 0.167 / 0.106** across Discovery / Validation / Reserve; Reserve selects 17 trades, captures 5/38 targets, and realizes about **-$2.83**
- tuned `f_new_oi_per_price` band ≈ **1.375–2.807** gives r ≈ **0.115 / 0.116 / 0.084**
- tuned `f_micro_volume_ratio_last_vs_prev10` band ≈ **1.654–3.111x** gives r ≈ **0.083 / 0.085 / 0.027**
- narrow timing/operational pockets may show higher precision but tiny coverage and must not be treated as market detectors

Therefore the weak T0 result is **not merely a bad default-threshold problem**. One-by-one nonlinear threshold tuning still does not produce a stable strong parameter. Preferred STRONG status remains `|r| >= 0.50` consistently; no feature passes.

Full methodology and result contract:
`research/strong_parameter_tuning/STAGE3C1_EXHAUSTIVE_SINGLE_PARAMETER_TUNING.md`


### Stage 3C.1B — winner anatomy & clustering

Stage 3C.1B tests whether weak aggregate correlation is caused by mixing different winner archetypes.

Frozen contrasts:
- all META_WIN (401) vs META_LOSS (835): best stable single-feature AUC floor ≈ **0.557**
- strong WIN (245) vs weak WIN (156): best stable AUC floor ≈ **0.531**
- strong WIN (245) vs META_LOSS (835): best stable AUC floor ≈ **0.549**

Therefore weak-WIN contamination is not the sole explanation; strong and weak WINs are themselves nearly indistinguishable at T0.

Unsupervised anatomy was fit only on the 162 Discovery strong winners and frozen before assigning Validation / Reserve winners. The best broad structure is **k=2**:

- **COUNTERFLOW_REVERSAL**: 65/245 strong winners (42 Discovery / 16 Validation / 7 Reserve), realized PnL **+$195.27**, average realized return **+0.601%**
- **FLOW_ALIGNED_CONTINUATION**: 180/245 strong winners (120 / 29 / 31), realized PnL **+$633.68**, average realized return **+0.704%**

The central finding is **signal cancellation**. Several parameters look random when all 245 strong winners are merged because the two archetypes use opposite directions:

- taker share: aggregate raw AUC ≈ **0.490**, counterflow ≈ **0.187** (LOW), continuation ≈ **0.599** (HIGH)
- 1m side return: aggregate ≈ **0.517**, counterflow ≈ **0.272** (LOW), continuation ≈ **0.605** (HIGH)
- flow support: aggregate ≈ **0.502**, counterflow ≈ **0.196** (LOW), continuation ≈ **0.612** (HIGH)

This confirms **winner heterogeneity**. It does not grant entry authority to either subtype. Counterflow has only 7 sealed-reserve targets, so its high subtype-specific AUC values are explicitly low-support evidence.

Stage 3C.2 should tune separate multi-parameter combinations for these two frozen archetypes instead of forcing one universal LONG winner rule.

Detailed research note:
`research/winner_anatomy/STAGE3C1B_WINNER_ANATOMY.md`


### Stage 3C.1C — LONG loss anatomy & failure clustering

Stage 3C.1C tests whether the **835 LONG META_LOSS** trades also contain distinct failure archetypes and then compares each failure type against the matching strong-WIN archetype from Stage 3C.1B.

Discovery-only clustering produces two broad LOSS archetypes:

- **FLOW_ALIGNED_FAILURE**: **602/835 (72.1%)**, split **344 / 119 / 139** across Discovery / Validation / Reserve
- **COUNTERFLOW_FAILURE**: **233/835 (27.9%)**, split **141 / 52 / 40**

This is nearly the same archetype composition as the strong-WIN population (**73.5% continuation / 26.5% counterflow**), so archetype identity alone is **not** a WIN/LOSS detector.

Within-archetype comparison is asymmetric:

- Flow-Aligned Continuation WIN vs Flow-Aligned Failure remains weak at T0; best stable single-feature AUC floor is about **0.551**
- Counterflow/Reversal WIN vs Counterflow Failure is materially more separable; examples include acceleration 5m-vs-15m AUC **0.648 / 0.655 / 0.696**, coin residual 5m-vs-BTC **0.644 / 0.636 / 0.832**, and selected slope5 norm **0.628 / 0.673 / 0.850** across Discovery / Validation / Reserve

Counterflow Reserve contains only **7 strong WINs**, so high Reserve AUC is explicitly low-support evidence and no rule is promoted to production.

Stage 3C.2 must therefore tune separate multi-parameter combinations for:

1. Flow-Aligned Continuation WIN vs Flow-Aligned Failure
2. Counterflow/Reversal WIN vs Counterflow Failure

Detailed research note:
`research/loss_anatomy/STAGE3C1C_LONG_LOSS_ANATOMY.md`

### Stage 3C.2 — archetype-specific multi-parameter combination

Stage 3C.2 tests 2-, 3-, and 4-parameter combinations separately inside the frozen archetypes rather than forcing one universal LONG formula.

#### 3C.2A — Flow-Aligned Continuation

Flow-Aligned remains the difficult T0 lane.

Best 2-parameter logistic combination:
- `f_median_abs_ret_5m_pct`
- `f_micro_rejection_wick_last`
- AUC Discovery / Validation / Reserve: **0.582 / 0.592 / 0.611**

Adding a third or fourth T0 parameter does not improve sealed Reserve. Rule combinations that look stronger on Discovery/Validation also deteriorate on Reserve.

Result: **FAIL for T0 multi-parameter separation**.

#### 3C.2B — Counterflow/Reversal

Counterflow is materially more structured.

Best 3-parameter logistic combination:
- `f_f_coin_residual_5m_vs_btc`
- `f_new_momentum_curvature`
- `f_gate_price_drift_pct`
- AUC Discovery / Validation / Reserve: **0.676 / 0.688 / 0.718**

This is predictive but not yet a stable STRONG detector because Validation remains below 0.70 and score-target correlation remains low.

A conservative research-only Counterflow failure veto fires only when all four are true:

1. `f_new_accel_5_vs_15 <= 0.6214308333`
2. `f_f_selected_slope5_norm <= 0.2612069909`
3. `f_f_coin_minus_market_30m >= -0.1486000362`
4. `f_f_coin_minus_market_15m <= 2.5904018610`

Performance:

- Discovery: catches **91/141 failures (64.5%)**, false-vetoes **13/42 strong WINs (31.0%)**, phi **0.285**
- Validation: catches **31/52 failures (59.6%)**, false-vetoes **4/16 strong WINs (25.0%)**, phi **0.294**
- Reserve: catches **29/40 failures (72.5%)**, false-vetoes **1/7 strong WINs (14.3%)**, phi **0.431**

Reserve retained pool improves from **7/47 = 14.9%** strong-WIN share to **6/17 = 35.3%**, but historical realized economics remain slightly negative: **-$5.92 total**, about **-0.070% per retained trade**.

Therefore Stage 3C.2 is **PARTIAL PASS, research-only**:

- Flow-Aligned: FAIL
- Counterflow: promising veto candidate, not final
- no production entry/veto authority changes
- do not force a final unified T0 LONG detector yet

Detailed research note:
`research/strong_microstructure/STAGE3C2_ARCHETYPE_COMBINATION.md`

### Stage 3C.3 — Flow-Aligned LONG temporal confirmation

Stage 3C.3 addresses the unresolved Flow-Aligned lane from Stage 3C.2 using causal T+1 / T+2 / T+3 confirmation.

Frozen subtype scope:

- **180 FLOW_ALIGNED_CONTINUATION strong WINs**
- **602 FLOW_ALIGNED_FAILURE losses**
- Counterflow 4-rule veto remains frozen and is **not retuned** in this stage.

Strict censoring is mandatory: a row is eligible at a temporal horizon only when `primary_label_end_ms > temporal_target_ms`. Primary model search excludes `confirm_mfe_pct` and `confirm_mae_pct` so the MFE>=1% target is not made tautological.

Eligible lane counts:

- T+1: **717 total / 169 strong WIN**
- T+2: **632 / 159**
- T+3: **545 / 143**

Best multi-parameter model AUC Discovery / Validation / Reserve:

- T+1: **0.637 / 0.647 / 0.682**
- T+2: **0.725 / 0.725 / 0.714**
- T+3: **0.754 / 0.831 / 0.722**

Therefore Flow-Aligned ambiguity is partly **temporal**: T+1 remains weak, T+2 becomes usable, and T+3 provides materially better separation.

A simpler T+3 observation is especially notable: `confirm_side_return_pct` alone has AUC **0.720 / 0.794 / 0.756**. At a threshold chosen for about 60% Validation target recall (approximately **+0.1585%** side return), sealed Reserve:

- selects **26/122** eligible trades
- captures **11/24** strong WINs (**45.8% recall**)
- has **42.3% target precision**
- includes **15 false positives**
- historical original-entry PnL **+$18.74**
- historical original-entry average return **+0.144% / trade**

Those economics are from the original frozen entries, not reconstructed delayed T+3 entries. The simpler feature looked better than the selected composite on sealed Reserve, but that simplification became obvious only after Reserve inspection and therefore requires a **fresh validation cohort** before promotion.

Stage 3C.3 verdict: **PARTIAL PASS, research-only**. No production entry/veto authority changes.

Detailed research note:
`research/temporal_confirmation/STAGE3C3_FLOW_ALIGNED_TEMPORAL_CONFIRMATION.md`

### New-data follow-up

A research-only microstructure feature engine also exists on branch `research/stage3c-microstructure` for feature families not present in the frozen cohort, including multi-level order-book imbalance, microprice edge, sub-minute AggTrade CVD, large-trade imbalance, CVD acceleration/persistence, flow-price efficiency and absorption proxies.

Historical L2/order-book values must never be fabricated for the frozen cohort. If the historical raw stream is unavailable, those features require forward causal collection.


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
│ Clario lane 1                 │ Clario lane 2                  │
│ gpt-5.6-sol                   │ gpt-5.6-sol                   │
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
stage12-v3.1-entry-boundary
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

The successor research line is **PP-DECISION V4 — High-Frequency Peak Capture** (`PP_DECISION_V4.md`). V4-1 uses one research-only 5-second Binance batch-ticker observer with no AI or trading authority. It persists `pp_v4_observation_cycles` / `pp_v4_peak_observations` and exposes `GET /pp-v4/stage1/summary` for audit. Stage 12 remains on its independent 15-second fast guard.


Stage12 v3.1 separates **market context** from **position-path excursion**. MFE/MAE and hard-stop excursion bounds only admit fully closed candles whose open timestamp is at or after the position entry timestamp, plus the current price. A candle that straddles entry is never allowed to contribute its full high/low to the position path. This prevents pre-entry price extrema from contaminating MFE/MAE while leaving market-context indicators unchanged.

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

## Stage 3C.5 unified LONG full-universe result

The current outcome-blind LONG architecture has now been tested against the full frozen **1,236 LONG** universe.

Frozen target remains **245 trades = META_WIN AND historical MFE >= 1.00%**.

Unified policy result:
- selected **345 / 1,236 = 27.9%**
- captured **114 / 245 strong WIN = 46.5% recall**
- false positives **231**
- precision **33.0%**
- baseline target prevalence **19.8%**
- precision enrichment **1.67x**

Chronological sealed Reserve:
- selected **61 / 248**
- captured **16 / 38 = 42.1% recall**
- false positives **45**
- precision **26.2%**
- split baseline target rate **15.3%**
- enrichment **1.71x**

Compared with the Stage 3B ~80%-validation-recall Reserve operating point, false positives fall from **137 to 45** and precision rises from **17.0% to 26.2%**, but captured strong WIN falls from **28 to 16**.

Therefore Stage 3C.5 is **PARTIAL PASS**: selectivity improves materially, but target recall remains too low for a final LONG detector.

Historical PnL on the selected rows is only an **original-entry reference**. It must not be treated as delayed-entry profitability for the Flow-Aligned T+3 lane; Stage 3C.4 already established that exact delayed-entry realized economics remain inconclusive without exact intraminute historical fills.
