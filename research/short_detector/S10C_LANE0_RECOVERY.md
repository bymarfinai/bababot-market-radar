# SHORT-S10C — Lane 0 Recovery

Status: **PASS — research frontier / no production authority**

## Objective

Recover the largest remaining SHORT coverage hole after S10A:

> **28 true Lane-0 strong WINs**

without rebuilding the SHORT detector from scratch.

Accepted baseline before S10C:

> **S10A: 655 → 268 OPEN → 51 / 99 strong WIN → 217 non-target**

S10B router override was rejected, so the S8 outcome-blind router remains frozen.

## Method

S10C does **not** scan new thresholds.

It reuses Lane-0 temporal rules whose thresholds were already frozen in SD-2B2. SD-2B2's primary Lane-0 D/V winner failed Reserve, but 13 secondary per-feature frozen rules later showed all-split robustness.

Because Reserve behavior of these rules was already known from SD-2B2, S10C is a **research-frontier recovery stage**, not a new sealed-holdout claim.

Seven unique classification signatures remained after removing equivalent aliases.

The efficient frontier was evaluated on routed Lane-0 candidates only.

## Accepted Lane-0 selector

For candidates with:

> `router_lane == 0`

select if either frozen rule fires causally:

### Rule A — T+3 micro-decay

> causal T+3 AND  
> `t3_f_micro_decay_3_vs_prev3 <= +0.2779031656624853`

### Rule B — T+2 coin-minus-market delta

> causal T+2 AND  
> `t2_delta_f_coin_minus_market_15m >= +0.032030968083884837`

Combined policy:

> **A OR B**

No threshold is retuned.

## Individual rule anatomy

### Rule A
- selected: 32
- strong WIN: 11
- true Lane-0 strong WIN: 10
- router-error strong WIN: 1
- non-target: 21
- precision: **34.38%**
- historical PnL: **+$1.43**

D/V/R strong WIN:
- Discovery: 7
- Validation: 3
- Reserve: 1

### Rule B
- selected: 51
- strong WIN: 15
- true Lane-0 strong WIN: 12
- router-error strong WIN: 3
- non-target: 36
- precision: **29.41%**
- historical PnL: **-$4.20**

D/V/R strong WIN:
- Discovery: 8
- Validation: 5
- Reserve: 2

Overlap:
- 22 selected
- 7 strong WIN

## Incremental S10C result

The union adds:

> **61 OPEN → 19 strong WIN → 42 non-target**

Composition of the 19 added strong winners:
- **15 true Lane-0 winners**
- **4 prior router-error Lane-1 winners**

Incremental metrics:
- precision: **31.15%**
- marginal cost: **3.21 entries / added strong WIN**
- historical realized-positive: 19
- historical PnL: **+$5.76**
- additional peak-MFE equivalent: **+$358.84**

This is materially more efficient than S10A's early-recovery layer:

> S10A: **8.43 entries / added strong WIN**  
> S10C: **3.21 entries / added strong WIN**

## Chronological behavior

### Discovery
Increment:
- +40 OPEN
- +10 strong WIN
- precision: 25.0%
- historical PnL: +$8.31

Cumulative:
- 200 OPEN
- 43 strong WIN

### Validation
Increment:
- +12 OPEN
- +6 strong WIN
- precision: **50.0%**
- historical PnL: +$0.39

Cumulative:
- 59 OPEN
- 17 strong WIN

### Reserve
Increment:
- +9 OPEN
- +3 strong WIN
- precision: **33.3%**
- historical PnL: -$2.93

Cumulative:
- 70 OPEN
- 10 strong WIN

The recovery mechanism therefore continues to add strong winners in all three chronological splits.

## Full cumulative SHORT funnel

Before S10C:

> **655 → 268 OPEN → 51 / 99 strong WIN → 217 non-target**

After S10C:

> **655 → 329 OPEN → 70 / 99 strong WIN → 259 non-target**

Metrics:
- strong-WIN recall: **70.71%**
- precision: **21.28%**
- historical realized-positive: **82**
- historical WR: **24.92%**
- historical original-entry PnL: **-$334.04**
- peak-MFE equivalent: **$1,372.26**

So S10C improves both:
- strong-WIN coverage: **51.5% → 70.7%**
- strong-target precision: **19.0% → 21.3%**

## Why the frontier stops here

The next Discovery-Pareto expansion was the frozen T+3 side-return rule:

> `t3_f_micro_side_ret_3m >= -0.05005005005005447`

Added beyond the accepted A OR B union:
- +23 OPEN
- +3 strong WIN
- marginal cost: **7.67 entries / added WIN**

Split:
- Discovery: +15 / +1 WIN
- Validation: +4 / +2 WIN
- Reserve: **+4 / +0 WIN**

It adds no Reserve winner and materially worsens marginal efficiency.

Therefore this extension is rejected.

## Remaining missed strong winners

After accepted S10C:

> **29 / 99 strong WIN remain missed**

Breakdown:
- true Lane 0 still missed: **13**
- routed Lane 1 with no same-threshold causal crossing: **15**
- router error still missed: **1**

## Verdict

> **SHORT-S10C = PASS as a research-frontier recovery layer.**

Accepted research baseline becomes:

> **655 → 329 OPEN → 70 / 99 strong WIN → 259 non-target**

This exceeds the LONG Stage3C.7A strong-target coverage rate:
- LONG: 150 / 245 = **61.2%**
- SHORT S10C: 70 / 99 = **70.7%**

However historical original-entry PnL remains negative, and the Lane-0 rules have no newly sealed holdout because their Reserve behavior was already observed in SD-2B2.

Next recovery target should be the remaining **15 routed Lane-1 winners with no same-threshold crossing**, while keeping the accepted S10C frontier frozen.
