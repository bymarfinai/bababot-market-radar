# Adaptive Profit Protection Discovery

**Project:** BabaBot Market Radar / Market Detektor  
**Research target:** Stage 12 profit protection after a position is already open  
**Status:** Stage 1 COMPLETE / Stage 2 READY  
**Frozen cohort cutoff:** 2026-09-29 20:11:58 WIB (1790687518406)  
**V3 research start boundary:** 1790662958358  
**Runtime at handoff:** PAUSE_ENTRIES; entries OFF; lifecycle exits ON. Always refresh runtime state before acting.

---

## 1. Purpose

This file is the source-of-truth and handoff document for the Adaptive Profit Protection Discovery workstream.

A new chat should be able to read README.md, BLUEPRINT.md, and this file and understand:
- why Stage 12 V3 profit protection needs research,
- what dataset has already been frozen,
- the complete 8-stage roadmap,
- exactly what Stage 2 must analyze,
- causal and anti-hindsight rules,
- required outputs and QA,
- what must not be changed during research.

This workstream is downstream of entry. It does not redesign Stages 1-11C unless the user explicitly decides to do so later.
---

## 2. Problem statement

Stage 12 V3 currently has three ordered deterministic layers:

~~~text
OPEN
  |
  v
Early Wrong-Direction Guard
  |
  v
Profit Protection / MFE Giveback Guard
  |
  v
Thesis Health
  |
  v
HOLD / REDUCE / CLOSE
~~~

The profit-protection layer works, but the frozen V3 cohort shows that large winning moves often give back too much before final exit.

Observed on the frozen 497-trade V3 cohort:
- MFE >= 2% trades: 54
- median peak-capture ratio for MFE >= 2%: about 33.7%
- median peak opportunity given back: about 66.3%
- about 85.2% of MFE >= 2% trades captured less than 50% of peak
- median MFE-peak to final-close time for MFE >= 2%: about 9m 39s
- MFE >= 5% trades: 11
- median peak-capture ratio for MFE >= 5%: about 33.9%
- median giveback share for MFE >= 5%: about 66.1%
Representative cases:

| Symbol | Peak MFE | Final net ROI | Approx. gap | Peak -> close |
|---|---:|---:|---:|---:|
| GRASSUSDT LONG | 23.50% | 12.85% | 10.64 pp | ~34.9m |
| ARXUSDT LONG | 9.71% | 3.14% | 6.56 pp | ~27.5m |
| CELOUSDT LONG | 10.28% | 4.50% | 5.78 pp | ~31.2m |
| BTWUSDT LONG | 6.84% | 0.68% | 6.16 pp | ~5.4m |
| MINAUSDT LONG | 6.57% | 3.41% | 3.17 pp | ~39.6m |
| CKBUSDT LONG | 4.70% | 1.58% | 3.12 pp | ~25.1m |

Important: MFE is a price-excursion metric while final ROI is net economic ROI after partial exits and fees. These are diagnostic comparisons, not accounting identities.

The research question is:

> Given peak profit size, continuation strength, time since peak, volatility, flow, positioning, and prior reduction state, how much profit should be allowed to give back before REDUCE or CLOSE?

---

## 3. Target concept: Adaptive Profit Protector V4

The intended architecture is an economic-PnL ratchet, not one static MFE threshold.
At time t:

~~~text
Economic PnL
= realized partial PnL
+ unrealized PnL on remaining quantity
- remaining allocated entry fee
- estimated exit fee / slippage
~~~

Track causally:

~~~text
PEAK_ECONOMIC_PNL_t
= max(Economic PnL from open through time t)
~~~

Conceptual adaptive lock:

~~~text
Lock Ratio
= Base Lock from Peak Size
+ Time-Since-Peak Tightening
+ Contradiction Tightening
- Continuation Bonus
- Volatility Allowance

Profit Floor
= Peak Economic PnL * Lock Ratio
~~~

Key principles:
- the floor tightens as a peak becomes stale or evidence deteriorates,
- a fresh strong runner may receive more breathing room,
- a new higher peak may raise the floor,
- the floor must not loosen merely because price falls,
- AI must not override a hard deterministic protection event,
- adaptive complexity is justified only if it beats a simpler static baseline out-of-sample.

Any illustrative coefficients discussed in chat are examples only, not approved production settings.
---

## 4. Eight-stage roadmap

### Stage 1 - Dataset Reconstruction
**Status: COMPLETE**

Freeze and reconstruct a causal research dataset for the V3 cohort.

### Stage 2 - Giveback Anatomy
**Status: NEXT**

Understand when, how quickly, and under which evidence states profitable trades start giving back peak economic PnL. No final parameter optimization.

### Stage 3 - Static Frontier Baseline

Sweep simple static protection rules first:
- arm threshold,
- fixed giveback ratios,
- peak tiers,
- REDUCE vs CLOSE behavior.

Adaptive logic must later outperform this baseline to justify complexity.

### Stage 4 - Adaptive Feature Discovery

Test which features add stable information about continuation vs giveback:
- peak size,
- time since peak,
- new-peak recency,
- 1m/3m structure,
- taker flow,
- OI,
- volatility,
- prior REDUCE state,
- higher-timeframe thesis context.
Discard features that do not add stable out-of-sample value.

### Stage 5 - Adaptive Lock Search

Search constrained adaptive formulas or tables.

Goals:
- improve economic peak capture,
- preserve big runners,
- avoid premature exits,
- improve net PnL after fees,
- avoid unstable parameter surfaces.

### Stage 6 - Walk-Forward Validation

Use chronological discovery / validation / untouched-test partitions. Never random-split the time series. Reject settings that work only in discovery.

### Stage 7 - Case Replay + Stress Test

Replay GRASS, CELO, ARX, MINA, PUMP-like runners, large reversals, and early wrong-direction losses frame-by-frame.

Stress higher fees/slippage, watcher delay, data gaps, and noisy flow/OI.

### Stage 8 - V4 Shadow Mode -> Production

V4 runs shadow-only beside V3 first. V3 remains action authority while V4 records hypothetical REDUCE/CLOSE. Only after live shadow comparison passes may V4 become production authority.
---

# 5. Stage 1 - Frozen dataset reconstruction

## 5.1 Frozen cohort

Permanent discovery cohort:

~~~text
V3 start:        1790662958358
snapshot cutoff: 1790687518406
closed trades:   497
unique symbols:  288
~~~

Do not append later trades to this discovery cohort. Later trades belong to validation/shadow cohorts.

## 5.2 Stage 1 outputs

~~~text
stage1_trade_master.csv
stage1_timeline_1m.csv
stage1_events.csv
stage1_coverage.csv
stage1_manifest.json
stage1_qa.json
~~~

Audit package:
https://radar.43-153-193-103.sslip.io/audit/stage1_adaptive_profit_protection_497trades.zip

SHA256:
bd6491e74c45a0859cc4b998f4e2aa85902cca76db45e4ecee028a5b552ca4a4
## 5.3 Stage 1 QA

| Item | Result |
|---|---:|
| Closed V3 frozen cohort | 497/497 |
| Unique symbols | 288/288 |
| Market-data failures | 0 |
| Causal 1m timeline rows | 12,688 |
| Exact lifecycle/order events | 4,503 |
| Persisted evaluations | 3,128 |
| FAST_GUARD evaluations | 931 |
| THESIS_5M evaluations | 1,919 |
| OPEN fills | 497 |
| REDUCE fills | 381 |
| CLOSE fills | 497 |
| OI coverage | 12,688 / 12,688 |
| Taker coverage | 12,678 / 12,688 |
| Negative time-since-peak rows | 0 |

Persisted evaluation density:
- median evaluations/trade: 4
- P90: 13
- max: 49

Therefore Stage 1 does not pretend to have continuous 15-second HOLD history.
## 5.4 Temporal truth hierarchy

### Exact event layer

Sources:
- position_evaluations
- paper_orders

Contains exact persisted:
- FAST_GUARD evaluations,
- THESIS_5M evaluations,
- OPEN,
- REDUCE,
- CLOSE,
- reasons,
- contradictions,
- persisted lifecycle snapshots.

### Reconstructed market-path layer

Sources:
- Binance USD-M closed 1m klines,
- Binance historical 5m Open Interest.

Contains minute-by-minute:
- OHLC,
- 1m / 3m return,
- taker-buy share,
- 5m OI change,
- realized volatility,
- rolling microstructure,
- partial realized PnL,
- remaining quantity,
- economic PnL if closed now,
- peak economic PnL,
- giveback dollars/ratio,
- time since economic peak.

Unpersisted 15-second HOLD ticks are never invented.
## 5.5 Reconstruction quality

Persisted MFE includes intraminute/ticker excursions, so it is expected to exceed peak return calculated from closed 1m candles.

Observed persisted-MFE minus reconstructed 1m-close peak:
- median: 0.173 pp
- mean: 0.264 pp
- P90: 0.604 pp

Keep this distinction visible in every later stage.

---

# 6. Stage 2 - Giveback Anatomy

## 6.1 Objective

Stage 2 is descriptive and diagnostic.

It must answer:

> After a trade becomes meaningfully profitable, what separates a healthy pullback that later continues from a giveback that should probably have been protected?

Stage 2 must not:
- choose final V4 thresholds,
- change production,
- optimize directly for final PnL,
- blend later trades into the 497-trade discovery cohort.

The output is a factual map of continuation vs decay that Stage 3 and Stage 4 will use.
## 6.2 Primary research questions

### Q1 - How much of the peak is normally lost?

For each trade and peak bucket quantify:
- peak economic ROI,
- final net ROI,
- capture ratio,
- giveback ratio,
- dollar giveback,
- percentage-point giveback.

### Q2 - How quickly does giveback happen after a peak?

Measure:
- exact fast-event timing where persisted,
- full-cohort closed-1m path,
- state at 1m / 3m / 5m / 10m / 15m after peak,
- time to first meaningful giveback,
- time to REDUCE,
- time to CLOSE,
- time to new peak.

### Q3 - What does successful continuation look like?

At and after peak analyze:
- repeated new peaks,
- side-adjusted 1m / 3m momentum,
- rolling structure,
- taker alignment,
- OI alignment,
- volatility,
- time since latest peak.
### Q4 - What changes before harmful giveback?

Look for deterioration in:
- price structure,
- taker flow,
- OI / positioning,
- momentum,
- volatility,
- time since peak,
- contradiction count.

### Q5 - Does the answer depend on peak size?

A +0.7% trade and a +10% trade must not be assumed to need the same breathing room.

### Q6 - Does prior REDUCE state change behavior?

Compare:

~~~text
OPEN / never reduced
vs
already REDUCED
~~~

A second protection breach after a REDUCE may deserve different handling.

### Q7 - Which trades are genuine runners?

Identify trades that make a meaningful new peak after a temporary giveback. The protector must not maximize capture by killing every runner early.

### Q8 - Which givebacks look clearly avoidable?

Identify cases where a meaningful economic peak existed, evidence deteriorated, the peak became stale, no meaningful new peak followed, and final capture collapsed.
---

# 7. Stage 2 analysis units

## 7.1 Trade-level unit

One row per completed trade.

Used for:
- peak/final outcome,
- total capture,
- total giveback,
- runner classification,
- final PnL.

## 7.2 Timeline-state unit

One causal row per reconstructed closed 1m timestamp, plus exact persisted lifecycle events.

Used for:
- evidence at time t,
- economic PnL at t,
- peak known at t,
- time since peak,
- current giveback,
- later continuation/reversal labels for research.

Future data may be used as labels only, never as input features.

---

# 8. Core Stage 2 definitions

## 8.1 Economic PnL

~~~text
economic_pnl_t
=
realized_partial_pnl_t
+ simulated net value of remaining position if closed at t
~~~

Stage 1 already incorporates allocated entry fee, paper exit-fee assumption, paper slippage assumption, and remaining quantity.
## 8.2 Peak economic PnL

~~~text
peak_economic_pnl_t
=
max(economic_pnl from open through t)
~~~

Must be causal. Never use a future peak to evaluate an earlier state.

## 8.3 Giveback

~~~text
giveback_usd_t
=
peak_economic_pnl_t - economic_pnl_t

giveback_ratio_t
=
giveback_usd_t / peak_economic_pnl_t
~~~

Giveback ratio is defined when the known peak is positive.

## 8.4 Final peak-capture ratio

~~~text
capture_ratio
=
final_net_pnl / peak_economic_pnl
~~~

Retain negative capture ratios. Do not clip them. Positive peak -> final loss is a critical failure class.

## 8.5 Time since peak

~~~text
time_since_peak_t
=
current time - timestamp of latest known peak economic PnL
~~~

Reset only when a new higher economic peak is made.
Starting research bins:

~~~text
0-1m
1-3m
3-5m
5-10m
10-20m
>20m
~~~

These are research bins, not production settings.

---

# 9. Mandatory peak buckets

Primary bucketing uses peak economic ROI:

~~~text
<0.5%
0.5-1%
1-2%
2-3%
3-5%
5-10%
>=10%
~~~

Also report persisted price-MFE buckets as a secondary diagnostic for continuity with earlier V3 analysis.

Small buckets must be clearly labeled and must not be treated as statistically stable.

---

# 10. Mandatory segmentation

Within peak buckets, analyze at least:

### Direction
LONG vs SHORT

### Position state
OPEN / not yet reduced vs REDUCED

### Time since peak
0-1m, 1-3m, 3-5m, 5-10m, 10-20m, >20m
### Taker state

Use side-adjusted states:

~~~text
ALIGNED
NEUTRAL
OPPOSITE
~~~

Preserve raw taker-buy-share values. Do not finalize V4 taker thresholds in Stage 2.

### OI / positioning state

Use side-adjusted states:

~~~text
ALIGNED
SUPPORTIVE / DELEVERAGING
NEUTRAL
OPPOSITE
~~~

Use only OI timestamps available at or before the row.

### Microstructure state

Use side-adjusted states such as:

~~~text
favorable break / new peak
consolidation / no break
break against position
~~~

### Volatility state

Use empirical realized-volatility quantiles, for example LOW / MID / HIGH / EXTREME.

Stage 2 must record actual quantile boundaries. Do not assume one absolute volatility threshold fits all symbols.
---

# 11. Research labels: continuation vs giveback

These labels may look forward because they are targets, not runtime features.

Create horizon labels at:

~~~text
+1m
+3m
+5m
+10m
+15m
~~~

## 11.1 New peak

~~~text
new_peak_within_H
=
future economic PnL exceeds current known peak within horizon H
~~~

## 11.2 Material continuation

Starting diagnostic definition:

~~~text
continuation_50bp_within_H
=
economic ROI improves by at least +0.50 percentage point within H
~~~

Run sensitivity at other reasonable levels. This is a research-label threshold, not a production setting.

## 11.3 Harmful giveback

Create separate labels for 25%, 50%, and 75% giveback of known peak within each horizon.
## 11.4 Peak-failure family

Retain separate labels:

~~~text
no_new_peak_before_close
new_peak_after_pullback
final_capture_below_25pct
final_capture_below_50pct
final_negative_after_positive_peak
~~~

Do not collapse these into one binary target too early.

---

# 12. Mandatory Stage 2 analyses

## 12.1 Peak-bucket outcome table

For each peak bucket report:
- N trades,
- wins/losses,
- gross PnL,
- fees,
- net PnL,
- median peak economic ROI,
- median final ROI,
- median capture ratio,
- median giveback ratio,
- median peak -> close time,
- median peak -> first REDUCE time,
- percent final negative after positive peak,
- percent that later create another peak.
## 12.2 Giveback decay curves

For each peak bucket calculate retained fraction after 1m, 3m, 5m, 10m, and 15m.

Report median / P25 / P75.

~~~text
retained_fraction_H
=
economic_pnl_(peak+H) / peak_economic_pnl
~~~

Also report probability of a new peak before each horizon.

This answers whether pullback is normally temporary or terminal.

## 12.3 Time-since-peak curves

For each time-since-peak bucket report:
- probability of a new peak in next 1/3/5m,
- probability of 25% / 50% / 75% giveback,
- expected future improvement,
- expected future drawdown,
- final capture distribution.

Key question:

> As a peak gets older, how quickly does useful continuation probability decay?
## 12.4 Evidence transition around peak

Compare available states around:

~~~text
T-3m
T-1m
T = peak
T+1m
T+3m
T+5m
~~~

Analyze:
- side-adjusted return,
- microstructure,
- taker share,
- OI change,
- realized volatility,
- contradiction count.

Separate RUNNERS vs GIVEBACK FAILURES.

## 12.5 Flow x OI interaction

Do not analyze flow and OI only independently.

Required matrix:

~~~text
FLOW aligned  + OI aligned
FLOW aligned  + OI opposite
FLOW opposite + OI aligned
FLOW opposite + OI opposite
FLOW neutral  + OI states
~~~

For each cell report continuation probability, new-peak probability, giveback severity, and final capture.
## 12.6 Volatility allowance analysis

For each volatility bucket ask:
- how large is normal pullback before continuation?
- how often does 20/30/40/50% giveback recover to a new peak?
- does high volatility justify more breathing room?
- at what point does breathing room become reversal?

The purpose is to determine whether a volatility allowance is empirically useful.

## 12.7 Already-reduced behavior

For states after a REDUCE event compare:
- probability of another new peak,
- final capture,
- time to close,
- second-giveback severity.

This tests the V3 principle:

~~~text
already REDUCED
+ another REDUCE-worthy deterioration
-> potentially CLOSE
~~~

Stage 2 describes whether the data supports this principle.
## 12.8 Runner casebook

Produce at least:
- top 10 peak-economic runners,
- top 10 final-PnL winners,
- top 10 largest givebacks,
- positive peak -> final loss cases,
- peak >=2% and capture >=70%,
- peak >=2% and capture <30%.

Each case should show a compact timeline:

~~~text
time
economic PnL / ROI
known peak
giveback
time since peak
taker
OI
structure
volatility
actual V3 action
~~~

Mandatory named examples where available:
- GRASSUSDT
- CELOUSDT
- ARXUSDT
- MINAUSDT
---

# 13. Stage 2 anti-hindsight / causality rules

## 13.1 No future data in features

At timestamp t:
- price data must have closed by t,
- OI timestamp must be <= t,
- partial REDUCE applies only after actual execution timestamp,
- exact lifecycle evidence appears only after it was persisted.

## 13.2 Future information only as labels

Future new high, final capture ratio, and future giveback are allowed as research targets only, never as input features.

## 13.3 Do not invent 15-second history

The dataset does not contain every V3 15-second HOLD poll.

Therefore:
- use exact persisted FAST_GUARD rows where available,
- use causal closed-1m reconstruction for continuous coverage,
- never forward-fill a missing FAST_GUARD decision as if it actually occurred.
## 13.4 Candle high/low are descriptive unless intrabar replay is explicit

For simulated decision rows, default to information from closed candles.

Do not use a candle's eventual high/low as if it were already known earlier within that candle.

## 13.5 Preserve the frozen cohort

Do not append trades closed after 1790687518406 to Stage 2 discovery.

## 13.6 No production parameter change

Stage 2 is research only.

Do not change V3 thresholds, enable live, or resume entries merely because a descriptive pattern looks attractive.

---

# 14. Required Stage 2 outputs

Minimum:

~~~text
stage2_trade_anatomy.csv
stage2_peak_bucket_summary.csv
stage2_decay_curves.csv
stage2_time_since_peak.csv
stage2_evidence_transition.csv
stage2_flow_oi_matrix.csv
stage2_volatility_analysis.csv
stage2_reduced_state_analysis.csv
stage2_casebook.csv
stage2_casebook.md
stage2_manifest.json
stage2_qa.json
~~~
Recommended package:

~~~text
stage2_giveback_anatomy_497trades.zip
~~~

The manifest must record:
- Stage 1 input package SHA256,
- frozen cutoff,
- peak bucket boundaries,
- volatility quantile boundaries,
- label definitions,
- missing-data counts,
- output row counts,
- code/version used.

---

# 15. Stage 2 acceptance criteria

Stage 2 is complete only if all conditions below pass.

## Data integrity
- all 497 frozen trades accounted for,
- timeline remains causal,
- negative time-since-peak count = 0,
- REDUCE-before-execution count = 0,
- OI lookahead count = 0,
- missing taker/OI explicitly reported.

## Descriptive completeness

For every meaningful peak bucket quantify:
- capture,
- giveback,
- decay over time,
- continuation frequency,
- time since peak,
- flow state,
- OI state,
- volatility state,
- reduction state.
## Runner protection

Explicitly identify conditions common to strong runners.

It is not acceptable to conclude only:

> tighter trailing is better.

## Giveback failure identification

Explicitly identify conditions common to trades that:
- reached meaningful profit,
- failed to create a new peak,
- gave back a large share,
- finished with poor capture.

## No premature optimization

Stage 2 must not select the final V4 lock table.

It may produce hypotheses and promising regions for Stage 3/4.

---

# 16. Expected Stage 2 conclusion

For each peak bucket, the final Stage 2 report should be able to state:
- normal breathing-room range,
- typical continuation window,
- how continuation probability decays with peak age,
- evidence states associated with continuation,
- evidence states associated with harmful giveback,
- effect of prior REDUCE,
- whether volatility justifies looser protection.

This becomes the factual basis for Stage 3 - Static Frontier Baseline and Stage 4 - Adaptive Feature Discovery.

Stage 2 ends with hypotheses, not production settings.
---

# 17. Overall V4 program targets

These are research ambitions, not Stage 2 pass/fail rules.

Current diagnostic baseline:

~~~text
MFE >=2% median capture ~33.7%
MFE >=5% median capture ~33.9%
~~~

Research ambition:

~~~text
meaningful peak >=2%:
    median capture around >=60% if robust

large runner cohort:
    median capture around >=70% if achievable
    without destroying continuation economics
~~~

Other desired outcomes:
- reduce positive-peak -> final-negative cases,
- improve net PnL after fees,
- preserve meaningful runners,
- reduce stale-peak giveback,
- avoid excessive churn and fee generation.

Targets may be revised if Stage 2-6 show they are unrealistic or harmful.
---

# 18. Instructions for a new chat

When continuing from a new chat:

1. Read README.md.
2. Read BLUEPRINT.md.
3. Read ADAPTIVE_PROFIT_PROTECTION_DISCOVERY.md.
4. Treat this file as source-of-truth for this discovery workstream.
5. Re-check runtime control state before touching production.
6. Do not rebuild Stage 1 unless QA/data corruption requires it.
7. Use the frozen 497-trade Stage 1 package and cutoff.
8. The next research stage is Stage 2 - Giveback Anatomy.
9. Stage 2 is descriptive; do not optimize final V4 thresholds yet.
10. Do not blend later trades into the 497-trade discovery cohort.
11. Do not claim continuous 15-second history where only 1m reconstruction exists.
12. Do not enable live trading.

Suggested new-chat instruction:

> Read README.md, BLUEPRINT.md, and ADAPTIVE_PROFIT_PROTECTION_DISCOVERY.md. Continue Adaptive Profit Protection Discovery from the recorded status. Do not alter the frozen 497-trade Stage 1 cohort. Execute the next requested stage according to the causal and QA rules in the discovery document.
---

# 19. Current handoff status

At document creation:

~~~text
Stage 1: COMPLETE / QA PASS
Stage 2: READY TO EXECUTE
Stage 3: NOT STARTED
Stage 4: NOT STARTED
Stage 5: NOT STARTED
Stage 6: NOT STARTED
Stage 7: NOT STARTED
Stage 8: NOT STARTED
~~~

Runtime at the time of handoff:

~~~text
mode             = PAUSE_ENTRIES
entries_enabled  = false
lifecycle_exits  = true
live             = disabled / disarmed
~~~

Runtime state is time-sensitive. Always refresh production before relying on it.