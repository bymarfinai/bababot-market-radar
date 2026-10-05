# SHORT-S10D — Remaining Lane-1 Recovery

Status: **PASS — research high-coverage frontier / no production authority**

## Objective

Recover the remaining routed-Lane-1 strong winners after S10C without lowering the frozen Lane-1 confirmation threshold globally.

Accepted baseline before S10D:

> **S10C: 655 → 329 OPEN → 70 / 99 strong WIN → 259 non-target**

Remaining strong winners before S10D:
- true Lane 0 still missed: 13
- routed Lane 1 with no accepted same-threshold crossing: **15**
- router error still missed: 1

## Residual Lane-1 anatomy

The residual routed-Lane-1 population contains:

> **201 candidates → 15 strong WIN → 186 non-target**

Split:
- Discovery: 110 → 8 strong WIN
- Validation: 49 → 5 strong WIN
- Reserve: 42 → 2 strong WIN

Crucial finding:

Of the 15 missed winners:
- **8** still have at least one causal T+1/T+2/T+3 snapshot
- **7** have **no causal temporal snapshot at all**

The two Reserve winners, GRASS and PHA, both resolve before T+1 is causal.

Therefore:

> a temporal-only S10D can never recover the Reserve winners.

This is not a threshold problem. It is an entry-timing / short-lived-winner problem.

## Recovery architecture

S10D therefore uses two causal lanes:

1. a **T0 fast-entry lane** using only rules whose thresholds were already frozen in earlier SHORT research;
2. a **T+3 alternate temporal rescue** for candidates that are not already accepted.

No threshold is newly fitted in S10D.

### T0 fast-entry rules

For routed Lane 1, fast-entry eligibility is the OR of:

1. **R7 — volume over range**
   `f_new_volume_over_range in [1.0170781185420166, 1.060973255243714]`

2. **R23 — momentum curvature**
   `f_new_momentum_curvature >= 1.2636050833333325`

3. **R79 — accel 15 vs 60**
   `f_new_accel_15_vs_60 in [0.6594, 1.7240119999999999]`

4. **R108 — breakdown magnitude**
   `f_context_breakdown_down_pct in [0.42735, 0.446816]`

5. **R107 — OI accel × overheat**
   `f_f_oi_accel_x_overheat in [-0.29188090961795327, -0.23281000377161334]`

6. **R119 — coin minus market 30m**
   `f_f_coin_minus_market_30m in [0.6909331187969325, 0.7639814635249487]`

### T+3 alternate rescue

For a routed-Lane-1 candidate not already opened by the fast lane or the existing same-threshold lane:

> causal T+3 AND  
> `t3_delta_micro_selected_vwap_extension_20 >= 0.0024105131797624857`

## S10D incremental result

S10D adds:

> **35 unique OPEN → 15 strong WIN → 20 non-target**

Metrics:
- incremental precision: **42.86%**
- marginal cost: **2.33 entries / added strong WIN**
- historical realized-positive: 14
- historical WR: 40.0%
- historical PnL: **-$7.21**
- additional peak-MFE equivalent: **+$200.68**

### By recovery lane

T0 fast lane unique increment:
- 30 OPEN
- 13 strong WIN
- 17 non-target
- precision: **43.33%**

T+3 alternate rescue:
- 5 OPEN
- 2 strong WIN
- 3 non-target
- precision: **40.0%**

## Chronological behavior

### Discovery
Increment:
- +20 OPEN
- **+8 strong WIN**
- +12 non-target
- precision: 40.0%

### Validation
Increment:
- +10 OPEN
- **+5 strong WIN**
- +5 non-target
- precision: **50.0%**

### Reserve
Increment:
- +5 OPEN
- **+2 strong WIN**
- +3 non-target
- precision: **40.0%**

Thus S10D recovers:

> **8 / 8 Discovery + 5 / 5 Validation + 2 / 2 Reserve routed-Lane-1 strong winners**

All 15 target winners are recovered in the research replay.

## Full cumulative detector

Before S10D:

> **329 OPEN → 70 / 99 strong WIN → 259 non-target**

After S10D:

> **364 OPEN → 85 / 99 strong WIN → 279 non-target**

Metrics:
- strong-WIN recall: **85.86%**
- precision: **23.35%**
- historical realized-positive: 96
- historical WR: **26.37%**
- historical original-entry PnL: **-$341.25**
- peak-MFE equivalent: **$1,572.94**

Relative to S10C:
- +35 OPEN
- +15 strong WIN
- +20 non-target
- strong-WIN recall: 70.7% → **85.9%**
- precision: 21.3% → **23.4%**

So both coverage and strong-target precision improve.

## Remaining missed strong winners

After S10D:

> **14 / 99 remain missed**

Breakdown:
- **13 true Lane-0 winners**
- **1 router-error winner**: ROBO
- **0 routed-Lane-1 residual winners**

The routed-Lane-1 recovery problem is therefore closed at the research-frontier level.

## Best-protector compatibility

The full 364 S10D cohort was replayed with the previously best SHORT protector:

> **V4.3 SHORT-LS4 + BE0.10 on the NO_ACTION lane**

### Full 364

| Policy | Wins | WR | PnL |
|---|---:|---:|---:|
| Historical | 96 | 26.37% | -$341.25 |
| V4.3 | 147 | 40.38% | -$329.15 |
| **V4.3 + BE0.10** | **140** | **38.46%** | **+$45.39** |

### Strong 85
Protected composite:
- 75 positive
- PnL: **+$168.16**

### Non-target 279
Protected composite:
- 65 positive
- PnL: **-$122.77**

### Chronological protected PnL

Discovery:
- **+$60.91**

Validation:
- **+$12.81**

Reserve:
- **-$28.33**

## S10C vs S10D protected economics

S10C best protector:
- **+$49.98**

S10D full-recovery best protector:
- **+$45.39**

Difference:

> **S10D is -$4.60 versus S10C on total protected PnL**

However:
- Validation improves from +$8.75 to **+$12.81**
- Reserve improves from -$31.06 to **-$28.33**
- Discovery declines from +$72.30 to **+$60.91**

Therefore S10D clearly improves winner coverage and holdout economics, but the extra Discovery false positives prevent it from becoming the final total-PnL operating point.

## Important execution caveat

The T0 fast lane fires on 83 routed-Lane-1 trades in the full universe.

Of those:
- 53 overlap trades that S10A would already select later
- 30 are unique fast-lane additions

Deploying the fast lane would therefore change entry timing for those 53 overlap positions.

So this stage is a **detector/research frontier**, not execution authority. A delayed-entry / fast-entry execution-realistic replay is still required before runtime promotion.

## Validation caveat

All thresholds used here were frozen in earlier research stages, but the S10D combination itself is selected after prior Reserve results were already available.

Therefore S10D does **not** constitute a newly sealed holdout validation.

## Verdict

> **SHORT-S10D = PASS as a high-coverage research frontier.**

Carry forward two facts:

1. Coverage frontier:
   > **364 OPEN → 85 / 99 strong WIN → 279 non-target**

2. Current best protected total-PnL operating point remains S10C:
   > **329 OPEN → 70 / 99 strong WIN → +$49.98 protected PnL**

The next stage should not add more recovery rules.

Proceed to:

> **SHORT-S10E — False-Positive Suppressor**

Primary objective:
- start from the S10D high-coverage candidate,
- remove as many of the 279 non-targets as possible,
- preserve at least ~95% of the 85 captured strong winners,
- evaluate D/V/Reserve and protected PnL,
- then select the final coverage-vs-precision operating frontier.
