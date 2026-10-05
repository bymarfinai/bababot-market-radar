# SHORT-S10J-6A — Primary V2 Non-Target Anatomy

Status: **ANATOMY COMPLETE — severe fallback cohort isolated**

## Objective

Dissect the remaining non-target population after S10J-5 Primary V2 before building any additional suppressor.

Frozen context:
- base detector: S10D
- Primary V2 suppressor from S10J-4
- V4.3 SHORT-LS4 + BE0.10
- fresh development window = opened S10H data
- no new veto promoted in this stage

## Primary V2 executable population

> **616 executable**

Composition:
- strong: **164**
- non-target: **452**

Protected PnL:
- strong: **+$449.04**
- non-target: **-$667.70**
- total: **-$218.66**

The non-target problem is therefore still the dominant source of negative economics.

---

# Non-target decomposition

The 452 non-targets are not equally harmful.

## Profitable non-targets

> **67 trades**

Protected PnL:

> **+$85.37**

These are not a priority for pruning.

## BE0.10 scratches

> **146 trades**

Protected PnL:

> **-$26.90**

Most are small scratch losses.

These are also not the main engineering target.

## Mild fallback losses

Historical-time fallback with protected PnL above -$2:

> **77 trades**

Protected PnL:

> **-$99.99**

Relevant, but secondary.

## Severe fallback losses

Historical-time fallback with protected PnL <= -$2:

> **163 trades**

Protected PnL:

> **-$625.18**

Average:

> **-$3.84 / trade**

This cohort is the primary remaining failure mode.

The severe fallback cohort alone represents approximately:

> **286% of the current total deficit**

Only about:

> **35% of its loss needs to be avoided to reach break-even**, assuming strong economics remain unchanged.

At the current average severe-loss size this is equivalent to approximately:

> **57 severe trades**

---

# Why fallback matters

Non-target Profit Protector outcome:

### FULL_CLOSE_050
- 66 trades
- all 66 protected-positive
- PnL **+$84.36**

### BE0.10
- 146 trades
- PnL **-$26.90**

### HIST_TIME_FALLBACK
- 240 trades
- only 1 positive
- PnL **-$725.16**

Therefore the remaining non-target issue is not:

> Profit Protector exits too early.

It is:

> **too many entries never develop enough favorable excursion to trigger the protector.**

These are effectively dead-on-arrival SHORT entries.

Fallback cohort MFE:
- median: **0.309%**
- 25th percentile: **0.183%**
- 75th percentile: **0.563%**

---

# Severe fallback by lane

| Lane | Primary V2 lane PnL | Severe fallback count | Severe fallback PnL | PnL if severe cohort were perfectly avoided |
|---|---:|---:|---:|---:|
| T0 | -$75.99 | 50 | **-$175.01** | +$99.02 |
| T+1 | -$66.14 | 39 | **-$160.84** | +$94.70 |
| T+2 | -$70.88 | **57** | **-$224.70** | **+$153.83** |
| T+3 | -$5.65 | 17 | -$64.62 | +$58.97 |

The highest-value target is therefore:

> **T+2 severe fallback**

Important counterfactual:

> removing only the 57 severe T+2 failures, with all other trades unchanged, would move total fresh Primary V2 from **-$218.66 to approximately +$6.04**.

This is diagnostic only, not an achievable assumption.

---

# Severe fallback stability by fresh day

## Oct 1
- severe: 70
- PnL: **-$271.34**

## Oct 2
- severe: 54
- PnL: **-$201.02**

## Oct 3
- severe: 39
- PnL: **-$152.81**

The failure exists on all three fresh days.

It is not a one-day anomaly.

---

# Causal feature anatomy

The analysis compares strong winners against severe fallback losers using normalized features available at or before each lane's decision point.

No future feature is used for a lane.

## T+2 — strongest evidence

The clearest separator is:

> **relative T+2 confirmation side-return**

Best representation:

`t2_confirm_side_return_pct__lrz64`

AUC strong vs severe fallback:

- Research Discovery: **0.569**
- Research Validation: **0.750**
- Research Reserve: **0.900**
- Fresh Oct 1: **0.689**
- Fresh Oct 2: **0.696**
- Fresh Oct 3: **0.658**

Direction:

> **6 / 6 blocks: stronger T+2 relative confirmation is associated with strong winners; weaker relative confirmation is associated with severe fallback.**

Mean AUC:

> **0.710**

This is currently the strongest transportable severe-loss separator found.

Other T+2 normalized versions of confirmation show the same 6/6 direction.

### Secondary T+2 feature

Relative coin-minus-market 30m is also useful in fresh data, but Discovery is inverted, so it is weaker as a standalone transportable rule.

Verdict:

> **T+2 relative confirmation is the first feature to test in the next severe-loss suppressor stage.**

---

# T0

Best stable candidate:

> **relative coin-minus-market 30m**

Example:
`f_f_coin_minus_market_30m__lpct64`

Direction is strong-winner higher than severe-fallback in all five blocks with sufficient sample.

Fresh effect is more modest than T+2.

Research Validation has too few severe examples for a valid AUC.

Verdict:

> useful secondary target, but weaker evidence than T+2.

---

# T+1

Best stable family:

> **OI acceleration × overheat, normalized relative to recent lane history**

Example:

`f_f_oi_accel_x_overheat__lrz64`

Strong-vs-severe AUC:
- Discovery: 0.786
- Reserve: 0.619
- Fresh Oct 1: 0.559
- Fresh Oct 2: 0.573
- Fresh Oct 3: 0.762

All five blocks with enough sample have the same direction.

Research Validation has insufficient severe sample.

Verdict:

> promising, but T+2 remains higher priority.

---

# T+3

Only 17 severe fallback trades remain after Primary V2.

Sample support is too small for a reliable six-block separator scan.

Given that T+3 total PnL is already close to neutral:

> **-$5.65**

T+3 should not be the next engineering priority.

---

# Engineering conclusion

The next suppressor should **not** target "all non-targets."

That would unnecessarily remove:
- profitable non-targets,
- harmless BE scratches,
- and potentially strong winners.

The correct target is:

> **severe fallback / dead-on-arrival entries**

Priority:

1. **T+2 severe fallback**
2. T0 severe fallback
3. residual T+1 severe fallback
4. leave T+3 alone initially

The best first causal discriminator is:

> **T+2 relative confirmation strength vs recent lane regime**

This is superior to the old S10G hard-band logic because:
- normalized rather than absolute;
- monotonic;
- causal;
- same direction across all six available chronological blocks;
- directly aligned with the economic failure cohort.

## Verdict

> **S10J-6A = anatomy complete.**

No new runtime or research veto is promoted yet.

Next recommended stage:

> **S10J-6B — T+2 Severe-Fallback Suppressor**

Goal:
- target the 57 severe T+2 fallback failures,
- preserve strong T+2 winners,
- use only stable normalized causal features,
- test multiple chronological blocks,
- replay execution-realistic PnL with frozen V4.3 + BE0.10,
- do not touch T0/T+1/T+3 until T+2 result is known.
