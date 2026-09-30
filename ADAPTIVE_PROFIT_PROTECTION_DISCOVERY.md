# Adaptive Profit Protection Discovery

**Project:** BabaBot Market Radar / Market Detektor  
**Research target:** Stage 12 profit protection after a position is already open  
**Status:** Stage 1 COMPLETE / Stage 2 COMPLETE / Stage 3 COMPLETE / Stage 4 COMPLETE / Stage 5 COMPLETE / Stage 6 RUNNING  
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
**Status: COMPLETE / QA PASS**

Understand when, how quickly, and under which evidence states profitable trades start giving back peak economic PnL. No final parameter optimization.

### Stage 3 - Static Frontier Baseline
**Status: COMPLETE / QA PASS**

Sweep simple static protection rules first:
- arm threshold,
- fixed giveback ratios,
- peak tiers,
- REDUCE vs CLOSE behavior.

Adaptive logic must later outperform this baseline to justify complexity.

### Stage 4 - Adaptive Feature Discovery
**Status: COMPLETE / QA PASS**

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
**Status: COMPLETE / QA PASS**

Search constrained adaptive formulas or tables.

Goals:
- improve economic peak capture,
- preserve big runners,
- avoid premature exits,
- improve net PnL after fees,
- avoid unstable parameter surfaces.

### Stage 6 - Walk-Forward Validation
**Status: RUNNING / PROSPECTIVE CLEAN PAPER COHORT**

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

# 13A. Stage 2 execution sequence

Stage 2 should be executed in the following order. A new chat must not skip directly to a later subsection unless the earlier subsection has passed its QA.

## Stage 2A - Peak / outcome anatomy

Purpose:
- establish the basic distribution of peak economic ROI,
- quantify final capture and giveback,
- separate small moves from meaningful runners.

Required work:
- assign every trade to the mandatory peak-economic-ROI bucket,
- calculate peak economic PnL / ROI,
- final net PnL / ROI,
- capture ratio,
- giveback dollars,
- giveback ratio,
- peak-to-close time,
- REDUCE count / state.

Minimum output:

~~~text
stage2_trade_anatomy.csv
stage2_peak_bucket_summary.csv
~~~

Do not yet use taker, OI, structure, or volatility to select a protector rule.

## Stage 2B - Giveback decay through time

Purpose:
- determine how quickly peak profit decays,
- determine whether a pullback commonly recovers to another peak.

Required horizons:

~~~text
+1m
+3m
+5m
+10m
+15m
~~~

For each peak bucket calculate:
- retained fraction,
- new-peak probability,
- 25% / 50% / 75% giveback probability,
- median / P25 / P75 economic PnL path.

Minimum output:

~~~text
stage2_decay_curves.csv
~~~

Key result:
- empirical continuation window for each peak-size bucket.

## Stage 2C - Time-since-peak hazard

Purpose:
- answer whether a stale peak becomes progressively less likely to continue.

Time-since-peak bins:

~~~text
0-1m
1-3m
3-5m
5-10m
10-20m
>20m
~~~

For every bin report:
- probability of new peak in next 1m / 3m / 5m,
- expected future upside,
- expected future downside,
- probability of >=25% / >=50% / >=75% giveback,
- final capture distribution.

Minimum output:

~~~text
stage2_time_since_peak.csv
~~~

This is the factual basis for any future time-decay tightening term.

## Stage 2D - Continuation evidence anatomy

Purpose:
- identify what strong runners look like while they are still healthy.

At minimum analyze:
- side-adjusted 1m return,
- side-adjusted 3m return,
- favorable / neutral / adverse microstructure,
- taker alignment,
- OI alignment,
- realized volatility,
- repeated-new-peak behavior.

Compare evidence around:

~~~text
T-3m
T-1m
T = peak
T+1m
T+3m
T+5m
~~~

Minimum output:

~~~text
stage2_evidence_transition.csv
~~~

The key question is not "what predicts profit in general?" but:

> What evidence is present when a profitable pullback is still likely to continue?

## Stage 2E - Flow x positioning interaction

Purpose:
- test whether taker and OI jointly distinguish continuation from exhaustion.

Required interaction matrix:

~~~text
FLOW aligned  + OI aligned
FLOW aligned  + OI supportive/deleveraging
FLOW aligned  + OI opposite

FLOW neutral  + each OI state

FLOW opposite + OI aligned
FLOW opposite + OI supportive/deleveraging
FLOW opposite + OI opposite
~~~

For each cell report:
- N,
- new-peak probability,
- continuation probability,
- median future upside,
- median giveback,
- final capture.

Minimum output:

~~~text
stage2_flow_oi_matrix.csv
~~~

Small-N cells must be marked unstable and must not be promoted into rules.

## Stage 2F - Volatility allowance anatomy

Purpose:
- determine how much breathing room is normal at different volatility levels.

Use empirical realized-volatility quantiles from the frozen cohort. Record the actual quantile cutoffs in the manifest.

For each volatility state test recovery after current giveback levels such as:

~~~text
20%
30%
40%
50%
60%
~~~

Questions:
- how often does price recover to a new peak?
- how much additional upside follows?
- how much downside follows if it fails?
- does high volatility genuinely require a looser lock?

Minimum output:

~~~text
stage2_volatility_analysis.csv
~~~

This stage may support or reject a future volatility allowance term.

## Stage 2G - Already-reduced state anatomy

Purpose:
- determine whether a position that has already been reduced should receive less tolerance on a second deterioration.

Compare:
- never reduced,
- recently reduced,
- reduced and then made a new peak,
- reduced and then failed to make a new peak.

Report:
- new-peak probability,
- future upside,
- future giveback,
- final capture,
- time from REDUCE to CLOSE,
- second-deterioration behavior.

Minimum output:

~~~text
stage2_reduced_state_analysis.csv
~~~

This stage tests the existing V3 escalation concept without assuming it is correct.

## Stage 2H - Casebook + synthesis

Purpose:
- translate aggregate statistics into understandable trade paths,
- prevent aggregate optimization from hiding destroyed runners.

Mandatory case groups:
- top 10 peak-economic runners,
- top 10 final-PnL winners,
- top 10 largest givebacks,
- positive peak -> final loss,
- peak >=2% and capture >=70%,
- peak >=2% and capture <30%.

Mandatory named cases where present:

~~~text
GRASSUSDT
CELOUSDT
ARXUSDT
MINAUSDT
~~~

Every case must show:

~~~text
timestamp
economic PnL
economic ROI
known peak
giveback ratio
time since peak
taker state
OI state
structure state
volatility state
position reduction state
actual V3 action
~~~

Minimum outputs:

~~~text
stage2_casebook.csv
stage2_casebook.md
~~~

The final Stage 2 synthesis must produce hypotheses in the form:

~~~text
OBSERVATION
    what the frozen data shows

POSSIBLE V4 IMPLICATION
    what this might imply for a protector

CONFIDENCE / LIMITATION
    sample size, reconstruction limit, or conflicting evidence
~~~

It must not output a final V4 lock table.

## Stage 2 substage completion rule

Stage 2 is not complete merely because all files exist.

Required order:

~~~text
2A -> 2B -> 2C -> 2D -> 2E -> 2F -> 2G -> 2H
~~~

After every substage:
1. report row/sample coverage,
2. report missing-data counts,
3. check causal timestamp rules,
4. record any small-N/unstable segments,
5. preserve the same frozen 497-trade cohort.

Only after 2H passes may the workstream proceed to Stage 3 Static Frontier Baseline.

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

# 17A. Stage 2 formal completion record

**Status: COMPLETE / QA PASS**

Audit package:

https://radar.43-153-193-103.sslip.io/audit/stage2_giveback_anatomy_497trades.zip

SHA256:

`4c7c9b35fc7a4ff6ff1bb6a894870ace13e0d0b82f1016dac64f18b6985fe47c`

Formal causal refinement:

- all 497 frozen trades are accounted for,
- 12,191 closed-1m rows remain after requiring candle close <= exact position close,
- 497 final overlapping candles that closed after the exact position exit are excluded from causal features,
- 18 sub-minute trades have no fully closed 1m candle before exit; they remain represented at trade/exact-event level and are never assigned fabricated 1m states,
- missing taker rows: 10,
- missing OI rows: 0,
- OI-lookahead rows: 0,
- REDUCE-before-execution rows: 0,
- negative time-since-peak rows: 0.

Empirical rv15 volatility quartiles used only for Stage 2 descriptive segmentation:

```text
Q25 = 0.092258%
Q50 = 0.129143%
Q75 = 0.183898%
```

Metric distinction is mandatory:

- persisted price MFE >=2% remains 54 trades and is the continuity diagnostic behind the earlier ~33.7% price-MFE capture observation,
- primary Stage 2 peak economic ROI >=2% contains 24 trades,
- median final economic capture for the primary >=2% cohort is ~57.15%,
- persisted MFE and economic peak ROI must never be treated as the same accounting measure.

Formal Stage 2 findings:

1. **Peak age matters.** In the primary 2-3% economic-peak bucket, probability of a new peak within the next 5m falls from ~75.5% at peak age 0-1m to ~32.1% at 3-5m and ~9.1% after >20m. In the 3-5% bucket it falls from ~63.2% at 0-1m to ~29.4% at 3-5m and ~4.4% after >20m.
2. **Giveback alone is not sufficient.** Healthy runners commonly pull back before continuing. Stage 2 therefore does not support a fixed giveback threshold as a standalone V4 exit trigger.
3. **Persistent adverse evidence separates failures better than a single 1m pullback.** At T+3m after the reference peak, GIVEBACK_FAILURE states show worse median side-adjusted 3m momentum (~-0.296% vs ~-0.107% for RUNNERS), more opposing taker flow (~53.3% vs ~36.2%), more opposing OI (~44.0% vs ~25.4%), more adverse structure (~17.3% vs ~9.4%), and median contradiction count 2 vs 1.
4. **Volatility is not automatically a breathing-room bonus.** At first 30% giveback across the cohort, LOW/MID rv15 states recovered to a new peak ~72%, HIGH ~50%, and EXTREME ~33%. This is descriptive only and must be tested causally in Stage 4 before any adaptive volatility allowance is approved.
5. **Prior REDUCE does not justify automatic CLOSE on a second breach.** Across already-reduced trades, roughly half of observed post-REDUCE 30-50% breaches still recovered to a new economic peak. A second breach therefore needs context/evidence, not only state memory.

Required Stage 2 outputs completed:

```text
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
stage2_report.md
```

Stage 2 ends with hypotheses only. Stage 3 must now establish the Static Frontier Baseline before adaptive feature or lock search is allowed.

---

# 17B. Stage 3 formal completion record

**Status: COMPLETE / QA PASS**

Audit package:

https://radar.43-153-193-103.sslip.io/audit/stage3_static_frontier_497trades.zip

SHA256:

`985bdc104c6bb9d23ab9383d8dacd694491dc1ce4133a5f92becfbae90e6ea57`

Static sweep:

```text
Global policies: 168
Tiered policies: 648
Total policies: 816
Pareto frontier policies: 47
```

Global arms tested:

```text
0.5%, 0.75%, 1%, 1.5%, 2%, 3%, 5%
```

Global giveback ratios tested:

```text
20%, 30%, 40%, 50%, 60%, 70%, 80%, 90%
```

Action modes:

```text
CLOSE_FIRST
REDUCE_ONCE
REDUCE_THEN_CLOSE
```

Tiered static scheme:

```text
0.5-2% peak economic ROI
2-5%
>=5%
```

with tier giveback values drawn from 30-80%.

Simulation invariants:

- causal closed-1m decisions only,
- 497 frozen trades remain unchanged,
- 12,191 strict pre-close 1m rows,
- 497 overlapping final candles that closed after exact position exit remain excluded,
- actual V3 REDUCE events are ignored inside the counterfactual policy state,
- synthetic REDUCE uses 50% remaining quantity,
- fee = 0.075%,
- adverse slippage = 2 bps,
- economic-PnL floor is ratcheted and cannot loosen,
- future opportunity peak is used only for evaluation, never as a trigger,
- exact actual V3 close timestamp/fill is the right-censor boundary,
- no continuation after the actual V3 exit is invented.

Baselines:

```text
ACTUAL_V3 total net PnL              = -257.28 USDT
FULL_HOLD_TO_V3_CENSOR total net PnL = -130.51 USDT
ACTUAL_V3 MFE>=2 price capture       = 33.67%
FULL_HOLD MFE>=2 price capture       = 38.64%
```

Static envelope:

- 724 / 816 policies beat actual V3 total net PnL.
- 46 / 816 policies beat full-hold-to-censor total net PnL.
- 43 policies reach >=60% median capture on the Stage 3 opportunity-economic-peak >=2% cohort.
- 11 policies reach >=65%.
- **0 policies reach >=70%**.
- 6 policies reach >=50% median capture against persisted MFE >=2%.
- **0 policies reach >=55% persisted-MFE >=2 capture**.

Key benchmark points:

### Net-PnL benchmark

```text
G_A5_GB20_CLOSE_FIRST
```

- total net PnL: **-74.06 USDT**
- delta vs actual V3: **+183.22 USDT**
- delta vs full-hold censor: **+56.45 USDT**
- economic-peak >=2 median capture: **57.51%**
- persisted-MFE >=2 median capture: **39.93%**
- persisted-MFE >=5 median capture: **57.21%**
- premature CLOSE on economic-peak >=2 cohort: **8.33%**
- trigger rate: **1.81% of trades**

This is the strongest observed static total-PnL benchmark and is deliberately low-intervention.

### Balanced capture benchmark

```text
G_A3_GB30_CLOSE_FIRST
```

- total net PnL: **-110.57 USDT**
- economic-peak >=2 median capture: **62.94%**
- persisted-MFE >=2 median capture: **41.64%**
- persisted-MFE >=5 median capture: **57.97%**
- premature CLOSE: **16.67%**
- trigger rate: **3.82%**

### Static capture ceiling

```text
G_A2_GB20_REDUCE_THEN_CLOSE
```

- total net PnL: **-116.84 USDT**
- economic-peak >=2 median capture: **68.51%**
- persisted-MFE >=2 median capture: **53.05%**
- premature CLOSE: **38.89%**
- premature REDUCE: **50.00%**

This rule reaches the highest observed static capture but does so by sacrificing too many runners.

Stage 3 conclusions:

1. **Static protection improves V3 materially but has a hard trade-off.** More aggressive protection raises capture while sharply increasing premature exits.
2. **A sparse protector can improve economics substantially.** The best total-PnL static rule acts on only ~1.8% of trades.
3. **Peak-tier complexity did not beat the best simple global rule on total PnL.** Static tiering is therefore not justified by this frozen cohort alone.
4. **REDUCE_ONCE preserves runner survival but gives up capture and net-PnL improvement relative to the strongest CLOSE_FIRST rules.**
5. **No static policy reaches the V4 research ambition.** The adaptive workstream must create value from causal state information, not from another fixed giveback retune.
6. The whole frozen 497-trade cohort remains negative under every tested static rule. Profit protection improves exit economics but cannot repair poor entry/loss trades by itself.

Required Stage 3 outputs:

```text
stage3_policy_results.csv
stage3_pareto_frontier.csv
stage3_benchmark_shortlist.csv
stage3_envelope_summary.csv
stage3_baselines.csv
stage3_selected_policy_trade_replay.csv
stage3_manifest.json
stage3_qa.json
stage3_report.md
```

Stage 4 must compare adaptive features against this static envelope under the same causal and right-censoring rules.

---

# 17C. Stage 4 formal completion record

**Status: COMPLETE / QA PASS**

Audit package:

https://radar.43-153-193-103.sslip.io/audit/stage4_adaptive_feature_discovery_497trades.zip

SHA256:

`12c30cb11059d82a450e6e5369512f60e9a70847e3843328f8d8395f312142e3`

Reproducible research script:

- branch: `research/adaptive-profit-protection-stage4`
- commit: `8e0e66ef46f14593da8336a70cfb19610d59c984`
- file: `research/adaptive_profit_protection_stage4.py`

Validation design:

```text
Frozen trades: 497
Strict causal closed-1m rows: 12,191
Post-close overlap rows excluded: 497
Split: DEV 60% / OOS-MID 20% / OOS-LATE 20%
Position split leakage: 0
Giveback anchors: 20%, 30%, 40%, 50%
First-30% anchor counts:
  DEV      = 164
  OOS-MID  = 43
  OOS-LATE = 39
```

The main Stage 4 screen uses all first-crossing states with a positive known economic peak. The economic-peak >=0.5% subset is kept as sensitivity-only because at the first-30% anchor it contains only 45 states, too sparse for robust two-holdout discrimination.

Future behavior is used only as the outcome label. Every predictor is known at or before the anchor.

Important methodological caveat:

- some nonlinear indicator forms were motivated by Stage 2 descriptive work on the same frozen cohort,
- therefore the Stage 4 OOS splits demonstrate **temporal stability inside the frozen cohort**, not a pristine external holdout,
- Stage 6 remains mandatory before production approval.

Final feature-family decisions:

```text
PEAK_SIZE        -> KEEP_STRONG
PEAK_RECENCY     -> KEEP_STRONG_NONLINEAR
MICRO_STRUCTURE  -> KEEP_STRONG_NONLINEAR
TAKER_FLOW       -> KEEP_STRONG_NONLINEAR
OI               -> KEEP_WEAK_CONDITIONAL
VOLATILITY       -> KEEP_WEAK_MODIFIER
PRIOR_REDUCE     -> DISCARD_AS_DERIORATION_EVIDENCE
HTF_THESIS       -> DEFER_LOW_COVERAGE
```

### Peak size

Peak size is the strongest stable base feature.

At first-30% giveback:

- incremental temporal-OOS AUC vs intercept-only baseline: about **+0.168**,
- combined-OOS bootstrap interval excludes zero.

Peak size therefore remains the primary context variable entering Stage 5.

### Peak recency / stale peak

Linear peak-age features alone were unstable, but the Stage-2-motivated nonlinear state `time_since_peak >= 3m` remained directionally terminal in both OOS windows.

At first-30% giveback:

- OOS-MID terminal-risk difference: about **+19.2 pp**,
- OOS-LATE: about **+37.1 pp**,
- combined OOS: about **+31.0 pp**.

Support is small, so stale-peak is retained as evidence, not as a standalone hard exit trigger.

### 3m adverse persistence

Side-adjusted 3m return <= -0.10% is one of the strongest stable deterioration signals.

Combined OOS at first-30% giveback:

- terminal-risk difference: about **+30.5 pp**,
- bootstrap 95% interval: approximately **+3.8 to +52.9 pp**.

This remains materially stronger than a single adverse 1m candle.

### Taker flow

The 45/55 opposing-taker state is the most consistently additive signal after conditioning on the other compact Stage 4 features.

Combined OOS:

- terminal-risk difference: about **+27.6 pp**,
- bootstrap interval: approximately **+5.9 to +48.5 pp**.

Conditional ablation reduces AUC in both OOS splits when opposing taker is removed.

### Open interest

Adverse OI-building remains directionally useful:

- combined-OOS terminal-risk difference: about **+25.8 pp**.

However:

- bootstrap interval crosses zero,
- the diagnostic definition overlaps adverse 3m persistence,
- raw OI incremental lift is small.

Therefore OI enters Stage 5 only as **conditional corroboration**, not a standalone hard trigger.

### Volatility

Extreme rv15 using the Stage 2 empirical-Q75 diagnostic boundary shows:

- combined-OOS terminal-risk difference: about **+23.6 pp**,
- bootstrap interval: approximately **+3.4 to +43.3 pp**.

But the continuous volatility family is not linearly stable and larger-peak support becomes weak. Volatility is therefore a **modifier**, not primary deterioration evidence.

This reverses the naive assumption that high volatility should automatically receive more breathing room.

### Prior REDUCE state

Prior REDUCE changes sign across holdouts and adds no stable deterioration information.

Therefore:

- do not use prior REDUCE itself as evidence that the trade is failing,
- retain it only as execution-state memory when deciding whether an action means REDUCE or CLOSE.

### Higher-timeframe thesis context

Fresh THESIS_5M evidence with <=10m staleness has only about **30.5%** coverage at the first-30% anchor and negative incremental OOS lift.

Therefore HTF thesis context is deferred from the core protector. It may be reconsidered later as an optional contextual layer, but Stage 5 must not depend on it.

### Evidence stacking

The strongest Stage 4 conclusion is that deterioration should be treated as a stack of causal evidence, not one fixed trigger.

Evidence primitives used in the diagnostic stack:

```text
stale peak >= 3m
3m side-adjusted return <= -0.10%
opposing taker 45/55
adverse OI-building
extreme rv15
micro-break against position
```

At first-30% giveback:

```text
OOS-MID:
  evidence count >=2 -> 70.6% terminal
  evidence count < 2 -> 34.6% terminal

OOS-LATE:
  evidence count >=2 -> 85.7% terminal
  evidence count < 2 -> 56.0% terminal
```

Evidence count >=3 reaches 66.7% terminal in OOS-MID and 100% in OOS-LATE, but support is only six states in each holdout, so this is not yet an approved threshold.

Conditional multifeature ablation indicates:

- opposing taker is the most consistently additive feature,
- volatility contributes mainly in OOS-LATE,
- stale peak, adverse 3m, and adverse OI overlap materially.

Stage 5 should therefore search **evidence stacks and lock/action policies**, not independent hard triggers for every feature.

Stage 3 hurdles remain unchanged:

```text
Best static total net PnL             = -74.06 USDT
Best static economic >=2 capture      = 68.51%
Best static persisted-MFE >=2 capture = 53.05%
```

Required Stage 4 outputs:

```text
stage4_anchor_dataset.csv
stage4_family_results.csv
stage4_feature_results_30pct.csv
stage4_keep_discard_summary.csv
stage4_primary30_descriptive.csv
stage4_bootstrap_30pct.csv
stage4_nonlinear_oos_screen.csv
stage4_nonlinear_bootstrap.csv
stage4_final_family_decisions.csv
stage4_evidence_stack.csv
stage4_conditional_ablation.csv
stage4_stage3_reference.csv
stage4_manifest.json
stage4_qa.json
stage4_report.md
```

Stage 4 does **not** select V4 lock percentages, action thresholds, REDUCE/CLOSE thresholds, or production coefficients.

Stage 5 must now search adaptive lock/action policies using only the promoted causal feature families and must beat the Stage 3 static frontier under the same causal and censoring rules.

---

# 17D. Stage 5 formal completion record

**Status: COMPLETE / QA PASS**

Audit package:

https://radar.43-153-193-103.sslip.io/audit/stage5_adaptive_lock_search_497trades.zip

SHA256:

`2850a4fb0a1846e267b0aebf93ac49f1ffc5b9b319e8b8f656015a063c56e8f0`

Research branch:

`research/adaptive-profit-protection-stage5`

Research commits:

- `b1242cec3ffbe13d007df2f7db52108bf1408c88` — Stage 5 search
- `6cf8d38e89d75023b863285ba6b0d6871a7fdc36` — Stage 5 frontier finalization

Search volume:

```text
Coarse policies:       576
Refined policies:      3,456
Local refinements:     810
Formal Stage 5 candidates: 3
```

Selection contract:

- DEV is the only ranking/selection partition.
- OOS-MID and OOS-LATE are temporal pass/fail gates.
- Full-cohort metrics are reporting only.
- Full-cohort "super-winners" discovered after inspecting OOS are diagnostic-only and cannot be promoted.
- Stage 6 must validate on later chronological cohorts outside the frozen 497 trades.

Formal candidates:

### S5-A — PRIMARY BALANCED

Policy:

`L_B0-25-50_T30+0_OI0.125_V0.025`

Interpretation:

```text
Base lock:
  0.5-2% peak  -> 0%
  2-5% peak    -> 25%
  >=5% peak    -> 50%

If core evidence count >=2:
  +30% lock tightening

Adverse OI corroboration:
  +12.5%

Extreme rv15 modifier:
  +2.5%

Continuation bonus:
  0%

Action:
  CLOSE_FIRST
```

Full frozen-cohort diagnostics:

- total net PnL: **-73.61 USDT**
- economic peak >=2 median capture: **65.48%**
- persisted-MFE >=2 median capture: **52.06%**
- economic peak >=2 premature CLOSE: **19.44%**
- economic peak >=5 median capture: **73.84%**
- economic peak >=5 premature CLOSE: **44.44%**
- DEV balanced gate: PASS
- OOS-MID balanced gate: PASS
- OOS-LATE balanced gate: PASS

S5-A is the formal primary candidate because it is the highest-DEV-net local policy that satisfies the predeclared DEV balanced gate and both OOS stability gates.

### S5-B — RUNNER PRESERVING

Policy:

`R_B0-30-50_T10+20_OI10_V+0_CB0_CLOSE_FIRST`

Full frozen-cohort diagnostics:

- total net PnL: **-79.69 USDT**
- economic peak >=2 median capture: **66.06%**
- persisted-MFE >=2 median capture: **53.33%**
- economic peak >=2 premature CLOSE: **16.67%**
- economic peak >=5 median capture: **69.59%**
- economic peak >=5 premature CLOSE: **33.33%**
- DEV balanced gate: PASS
- both temporal OOS gates: PASS

S5-B is retained because it gives up some PnL while reducing big-runner premature-close risk.

### S5-C — CAPTURE HEAVY

Policy:

`L_B0-30-50_T25+5_OI0.125_V0.000`

Full frozen-cohort diagnostics:

- total net PnL: **-77.20 USDT**
- economic peak >=2 median capture: **67.03%**
- persisted-MFE >=2 median capture: **53.33%**
- economic peak >=2 premature CLOSE: **19.44%**
- economic peak >=5 median capture: **72.25%**
- economic peak >=5 premature CLOSE: **44.44%**
- DEV balanced gate: PASS
- both temporal OOS gates: PASS

Static-frontier comparison:

```text
Stage 3 static-net:
  PnL     = -74.06 USDT
  capture = 57.51%
  premC   = 8.33%

Stage 3 static-balanced:
  PnL     = -110.57 USDT
  capture = 62.94%
  premC   = 16.67%

Stage 3 static-capture:
  PnL     = -116.84 USDT
  capture = 68.51%
  premC   = 38.89%
```

All three formal Stage 5 candidates have:

```text
static policies dominating them on net + capture = 0
static policies dominating them on net + capture + premature close = 0
```

Therefore Stage 5 expands the Stage 3 static Pareto frontier rather than merely retuning a static threshold.

Primary-candidate surface check:

```text
local neighborhood policies = 324
within primary -10 USDT PnL and -3pp capture = 108
```

This is evidence against a single-point parameter spike.

Important limitations:

1. the frozen 497 trades remain the discovery cohort;
2. Stage 4 already inspected OOS-MID/OOS-LATE, so these are stability gates, not pristine unseen tests;
3. economic-peak >=5 has only 9 trades, so big-runner premature-close estimates are noisy;
4. no Stage 5 policy is approved for production;
5. no Stage 5 policy is approved for V4 shadow authority yet;
6. Stage 6 later-cohort chronological validation is mandatory.

Stage 6 must carry **all three formal candidates** forward and must not tune them further against the frozen Stage 5 OOS windows.

---

# 17E. Stage 6 readiness / boundary-overlap audit

**Formal status: BLOCKED / WAITING CLEAN POST-CUTOFF COHORT**

Audit package:

https://radar.43-153-193-103.sslip.io/audit/stage6_walkforward_readiness_bridge21.zip

SHA256:

`3aaa6470860213cf96ffd610beddcb703727513e12bdb64d3cd271a3aaf8cf98`

Research branch:

`research/adaptive-profit-protection-stage6`

Research commits:

- bridge reconstruction: `00cb3a45312b29b87ebdb53688836a94fd3a2c8b`
- bridge evaluator: `1a3c8fad03125e049daf5d8bdcd08645d54ca0a6`

Discovery cutoff remains:

`1790687518406`

Current post-cutoff inventory:

```text
positions closed after cutoff:                 21
positions opened after cutoff:                  0
boundary-overlap positions:                    21
clean Stage 6 validation trades:                0
untouched Stage 6 test trades consumed:         0
```

All 21 positions that closed after the cutoff were already open before the cutoff. Because the adaptive lock is path-dependent from trade open through the running economic peak/floor, these boundary-overlap positions are **not** a clean chronological Stage 6 validation cohort.

Therefore:

- do not count the 21 bridge positions toward formal Stage 6 acceptance,
- do not tune Stage 5 parameters from these results,
- keep S5-A / S5-B / S5-C frozen,
- preserve the untouched-test cohort.

Bridge reconstruction is complete:

```text
trades: 21
symbols: 21
strict market-data reconstruction: complete
closed-1m rows: 1,699
market-data failures: 0
```

Bridge diagnostic only:

```text
S5-A:
  net PnL              +93.74 USDT
  win rate              52.38%
  economic >=2 trades        4
  median capture        74.75%
  premature close      100.00%

S5-B:
  net PnL              +65.78 USDT
  median capture        57.41%
  premature close      100.00%

S5-C:
  net PnL              +65.78 USDT
  median capture        57.41%
  premature close      100.00%

STATIC_NET:
  net PnL              +91.74 USDT
  median capture        74.15%
  premature close       25.00%

STATIC_BALANCED:
  net PnL             +112.02 USDT
  median capture        84.74%
  premature close        0.00%

ACTUAL_V3:
  net PnL              +89.82 USDT
```

Interpretation:

- S5-A is slightly above Actual V3 on bridge total PnL,
- STATIC_BALANCED is materially better in this 21-trade bridge,
- only four bridge trades reached economic peak >=2%, so the large-runner metrics are extremely underpowered,
- S5-A/B/C all close those four before the whole-trade opportunity peak,
- this is a **runner-risk warning** for Stage 6/7, not a formal rejection from a clean test.

Clean Stage 6 eligibility rule:

```text
opened_at_ms > 1790687518406
```

Stage 6 can formally resume only when paper trades satisfying that rule exist.

No Stage 5 parameter may be changed while waiting for the clean validation cohort.

Production was not modified by this readiness audit.

---

# 17F. Stage 6 prospective activation record

**Status: RUNNING / CLEAN COHORT COLLECTION ACTIVE**

Deployment:

```text
main merge commit = 68ab376ddf091acd1e9dd96cf5bd5f8c1762e062
Stage 6 version   = stage6-prospective-shadow-v1
run ID            = stage6-prospective-1790740200126
Stage 6 start ms  = 1790740200126
discovery cutoff  = 1790687518406
```

Eligibility rule:

```text
opened_at_ms > 1790740200126
```

Activation checks:

- deployed container full test suite: **136 / 136 PASS**,
- Stage 6 recorder enabled before entries resumed,
- initial Stage 6 summary: **0 registered / 0 open / 0 closed**,
- control mode changed from `PAUSE_ENTRIES` to `RUN` only after the zero-state check,
- paper entries enabled,
- lifecycle exits enabled,
- live trading remains disarmed and disabled,
- public summary endpoint verified:
  `https://core-prod.43-153-193-103.sslip.io/stage6/summary`.

Authority / comparison contract:

- actual paper lifecycle authority remains `V3_CONTROL`,
- frozen S5-A / S5-B / S5-C run causal closed-1m shadow lanes,
- STATIC_NET / STATIC_BALANCED / STATIC_CAPTURE run in parallel,
- lanes use the same entry, quantity, fee and slippage assumptions,
- a policy lane may close itself earlier,
- an unclosed lane is right-censored at exact V3 control close,
- Stage 6 parameters are frozen and may not be tuned from ongoing results.

The prior 21 boundary-overlap trades remain diagnostic-only and are not part of this prospective cohort.

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
8. Stages 2, 3, 4, and 5 are COMPLETE / QA PASS. Stage 6 prospective validation is RUNNING with a fresh start boundary; only positions opened after the Stage 6 start timestamp are eligible.
9. Stage 2 is locked as descriptive anatomy, Stage 3 as the static benchmark envelope, Stage 4 as the feature-screen contract, and Stage 5 as the adaptive candidate frontier. None is approved for production.
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
Stage 2: COMPLETE / QA PASS
Stage 3: COMPLETE / QA PASS
Stage 4: COMPLETE / QA PASS
Stage 5: COMPLETE / QA PASS
Stage 6: RUNNING / PROSPECTIVE CLEAN PAPER COHORT
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

## V5-0 — Sub-1% prospective decision gate

V5-0 extends the research to trades that make meaningful but sub-1% economic MFE before fading. The design is prospective-first rather than another historical optimization loop. It arms at 0.50% economic MFE, watches 30-50% giveback, forces a HOLD/REDUCE/CLOSE decision at >=50% giveback using momentum/structure/taker/OI evidence, and uses a 100% giveback hard stop. Once peak economic MFE reaches 1.00%, V5-0 no longer intervenes; the >=1% logic is reserved for V5-1. V5-0 remains a shadow lane; V3 remains paper authority.
