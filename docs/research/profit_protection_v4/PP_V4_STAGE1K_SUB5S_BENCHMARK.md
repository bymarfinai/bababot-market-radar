# PP V4-1K — Clean Residual Sub-5s Benchmark

Status: **COMPLETE — OFFLINE INFORMATION-LAYER RESEARCH ONLY**

## Question

Can 2-second or 1-second periodic current-price observation materially compress the clean Stage1J residual lower tail, or is an event-driven/tick observer required?

## Frozen cohort

Stage1J clean eligible trades:
- clean post-entry MFE >= +0.30%: **99**

Residual 5s lower tail:
- archived actual 5s capture <80%: **24 / 99 = 24.24%**

The 24 Stage1K trades match the 24 Stage1I genuine residual trades **exactly**.

## Method

Price source:
- Binance USD-M Futures 1m klines to locate candidate minutes;
- Binance USD-M Futures aggregate trades for exact post-entry prices inside candidate minutes.

Counterfactual periodic cadences:
- 5,000 ms diagnostic
- 2,000 ms
- 1,000 ms

Polling phase was not cherry-picked.

Every cadence was tested on a 100 ms phase grid:
- 5s: 50 offsets
- 2s: 20 offsets
- 1s: 10 offsets

A sample only sees the latest aggregate-trade price available **at or before** its timestamp.

For the decision gate, 1s/2s must reach the threshold using their **own scheduled samples**. The archived 5s peak cannot rescue a failing phase.

Expected rescue counts assume polling phase is uniformly distributed across the tested offsets.

Event-driven/tick is reported only as an observability upper bound, not executable PnL.

## Preregistered decision target

Baseline clean lower tail:

`24 / 99 = 24.24%`

To reduce overall clean capture <80% to <=10%, at least **15 of the 24 residual trades** must be rescued to >=80%.

The slowest cadence meeting that target would be selected.

If neither 2s nor 1s meets it, periodic polling is rejected for this objective and event-driven observation becomes the next research candidate.

## Result

| Observer | Expected residual rescues to >=80% | Residual rescue rate | Projected overall <80% |
|---|---:|---:|---:|
| 5s phase diagnostic | 2.68 / 24 | 11.17% | 21.54% |
| 2s periodic | **5.60 / 24** | **23.33%** | **18.59%** |
| 1s periodic | **8.30 / 24** | **34.58%** | **15.86%** |
| Event-driven/tick upper bound | 24 / 24 | 100% | 0% theoretical |

Required:
- >=15 / 24 expected rescues
- projected overall <80% <=10%

Decision:
- **2s periodic: FAIL**
- **1s periodic: FAIL**
- **event-driven/tick: NEXT RESEARCH CANDIDATE**

The event-driven row is not a production promise. It is the historical information upper bound because every aggregate trade is observable offline.

## Higher capture thresholds

Expected rescues among the 24 residual trades:

| Cadence | >=80% | >=90% | >=95% |
|---|---:|---:|---:|
| 5s diagnostic | 2.68 | 0.66 | 0.42 |
| 2s | **5.60** | **1.65** | **1.05** |
| 1s | **8.30** | **3.30** | **2.10** |

Even at 1s, >=90% peak capture remains rare across arbitrary polling phase.

## Phase robustness

### 2-second polling

Across the 24 trades:
- median probability of capturing >=80%: **10%**
- >=80% in every tested phase: **2 trades**
- >=80% in at least 80% of phases: **2 trades**
- >=80% in at least 50% of phases: **5 trades**
- zero chance of >=80% on the tested phase grid: **8 trades**

### 1-second polling

Across the 24 trades:
- median probability of capturing >=80%: **20%**
- >=80% in every tested phase: **4 trades**
- >=80% in at least 80% of phases: **6 trades**
- >=80% in at least 50% of phases: **7 trades**
- zero chance of >=80% on the tested phase grid: **8 trades**

Therefore 1s is better than 2s, but the remaining flashes are still too short and phase-sensitive for 1s periodic polling to solve the tail.

## LONG vs SHORT

Residual population:
- LONG: **13**
- SHORT: **11**

### 1s expected >=80% rescue

LONG:
- expected rescues: **6.0 / 13**
- rescue rate: **46.15%**
- zero-probability trades: **4**

SHORT:
- expected rescues: **2.3 / 11**
- rescue rate: **20.91%**
- zero-probability trades: **4**

SHORT remains substantially harder.

### 2s expected >=80% rescue

LONG:
- **3.9 / 13 = 30.0%**

SHORT:
- **1.7 / 11 = 15.45%**

## 1-second hard residuals

Eight trades had **0% probability** of reaching >=80% on any tested 1s phase:

- C98USDT SHORT
- ARUSDT SHORT
- CUSDT LONG
- BTWUSDT LONG
- CTSIUSDT LONG
- ONUSDT SHORT
- CUSDT LONG
- PHAUSDT SHORT

This is consistent with Stage1I's finding that many true peak regions last <=1 second.

## Interpretation

The clean benchmark establishes three things:

1. **5s was a real improvement over 15s.**
2. **1s is better than 2s**, but periodic phase still dominates many flash excursions.
3. The remaining information problem is no longer well-described as "poll faster." A meaningful part of the tail requires observation triggered by market events/ticks rather than a wall-clock sample.

Therefore the next research step should test a **single canonical event-driven Binance Futures trade/price stream**, with no trading authority, against:
- clean post-entry MFE;
- current 5s observer;
- missing-event/data-quality rates;
- event-to-observation latency;
- lower-tail compression.

## Decision

> **Do not deploy 2s or 1s periodic polling as the solution.**

Both fail the preregistered target.

> **Next: V4-1L — Event-Driven Observability Benchmark.**

Protection/exit formula engineering remains blocked until the information layer is validated.

## Frozen artifacts

- preregistration:
  `docs/research/profit_protection_v4/PP_V4_STAGE1K_SUB5S_BENCHMARK_CONTRACT.md`
- evidence reconstruction:
  `research/profit_protection_v4/stage1k_fetch_phase_evidence.py`
- evaluator:
  `research/profit_protection_v4/stage1k_sub5s_phase_benchmark.py`
- frozen phase evidence:
  `research/profit_protection_v4/results/stage1k_sub5s_phase_benchmark_evidence.json`
- frozen result:
  `research/profit_protection_v4/results/stage1k_sub5s_phase_benchmark.json`
