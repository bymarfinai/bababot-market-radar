# PP-DECISION V3 — Stage 2B.1 Fast Peak Observation Lane

Status: **IMPLEMENTED — prospective shadow capture only, no exit authority**

## Objective

Stage 2B found two independent blockers:

1. 38.04% of clean terminal candidates were already beyond the 20% giveback budget at the first ~15-second post-peak observation.
2. Inside the <=20% safe window, the existing context features had weak late-cohort separation between terminal peaks and future continuation.

Stage 2B.1 therefore improves observation resolution before changing any exit rule.

Primary questions:

- Does a 5-second current-price lane observe a materially higher fraction of true MFE than the existing ~15-second lane?
- Does the 5s/10s/15s micro-path create usable causal separation between terminal decay and continuation while giveback is still <=20%?

## Runtime design

Stage 2B.1 is a parallel **ticker-only shadow observer**.

It does not:

- call REDUCE or CLOSE;
- change Stage 12 fast-guard cadence;
- change PP-LEGACY V3;
- change PP-DECISION V2;
- create paper or live orders;
- use candle highs as executable prices;
- use future MFE in a runtime decision.

For each open PAPER position opened after the activation boundary, the lane samples Binance current ticker price at a target cadence of 5 seconds and persists:

- observed timestamp;
- symbol / side / entry price;
- current market price;
- current PnL;
- previous observed PnL;
- PnL delta from previous sample;
- causal running observed peak;
- timestamp of the running peak;
- giveback from running peak;
- seconds since peak;
- actual sample gap;
- whether the causal running peak has crossed the +0.30% research arm threshold.

The table is:

`pp_v3_fast_peak_observations`

## Configuration

```text
PP_V3_STAGE2B1_ENABLED=false
PP_V3_STAGE2B1_START_MS=0
PP_V3_STAGE2B1_POLL_SECONDS=5
PP_V3_STAGE2B1_ARM_PCT=0.30
PP_V3_STAGE2B1_WORKERS=5
```

Safety behavior:

- default is OFF;
- the loop will not start without an explicit positive start boundary;
- only positions with `opened_at_ms > PP_V3_STAGE2B1_START_MS` are included;
- observation is read-only with respect to position/order state.

## Read-only audit endpoint

```text
GET /pp-v3/stage2b1/summary
```

The endpoint exposes:

- configured start boundary;
- configured cadence;
- row count;
- distinct captured positions;
- number of armed observations;
- first/last observation timestamps;
- recent samples.

## Prospective evaluation contract

The lane must accumulate a clean new cohort. Evaluation happens only after positions close.

For each captured trade, compare:

1. **5s observable peak**
   - maximum `current_pnl_pct` from `pp_v3_fast_peak_observations`.

2. **existing ~15s observable peak**
   - maximum current-PnL observation from the existing PP-V2 fast stream.

3. **true MFE**
   - offline lifecycle MFE benchmark after close.

Primary observability metrics:

- median 5s observable peak / true MFE;
- notional-weighted 5s observable peak / true MFE;
- improvement versus the existing ~15s observable peak;
- share of trades where 5s observed peak reaches >=80%, >=90%, >=95% of true MFE.

Primary peak-recognition metrics:

- terminal-vs-continuation separation at first 5s, 10s, and 15s after a record peak;
- share of terminal candidates still inside <=20% giveback at each horizon;
- runner false-exit frontier using only features that existed by the evaluated timestamp.

## Promotion gate

Stage 2B.1 itself has **no production promotion path**. It is data acquisition and observability research.

Stage 2C remains blocked until the new cohort demonstrates both:

- materially better peak observability than the current ~15s lane; and
- materially better early terminal-vs-continuation separation inside the <=20% giveback window.

No result may be backfilled from unobserved historical 5-second prices.

## Reproducibility / implementation

- runtime observer: `market_radar/profit_protection_v3_fast_observer.py`
- startup hook: `market_radar/__main__.py`
- read-only endpoint: `GET /pp-v3/stage2b1/summary`
- tests: `tests/test_pp_v3_stage2b1_fast_peak_observer.py`
