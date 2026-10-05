# SHORT-S10J-6B — T+2 Severe-Fallback Suppressor

Status: **PASS targeted T+2 repair / FAIL overall profitability / no production promotion**

## Objective

S10J-6A showed that the remaining SHORT deficit after Primary V2 is dominated by severe fallback losers.

Primary V2 fresh:
- 616 executable
- 164 strong
- 452 non-target
- protected PnL: **-$218.66**

Severe fallback non-targets:
- 163 trades
- protected PnL: **-$625.18**

T+2 severe fallback alone:
- 57 trades
- PnL: **-$224.70**

S10J-6B therefore targets **only T+2 severe fallback**.

T0, T+1 and T+3 remain unchanged.

Frozen:
- S10D base
- Primary V2 from S10J-4
- V4.3 SHORT-LS4 + BE0.10
- execution timing from S10J-5
- causal rolling normalization

No Profit Protector parameter is changed.

---

# Search design

The strongest S10J-6A separator was relative T+2 confirmation strength.

Single-threshold rules were tested first.

Result:

> single thresholds either preserved winners but removed almost no severe failures, or removed meaningful severe failures only by sacrificing too many strong winners.

Therefore S10J-6B tested low-complexity monotonic **AND** rules:

> weak relative T+2 confirmation  
> **AND**  
> a second weakness / contradiction signal

Maximum complexity remained two signals for the accepted rule.

A final OR-of-two-clauses scan was also tested. It did not provide enough additional value to justify four-signal complexity.

---

# Accepted stable rule

For **T+2 only**, veto when both are true:

> `t2_confirm_side_return_pct__lpct64 <= 0.35`

AND

> `f_gate_price_drift_pct__pct128 >= 0.60`

Interpretation:

1. T+2 confirmation is in the lower 35% relative to the prior 64 T+2-lane observations.
2. Gate price drift is simultaneously in the upper 40% relative to the prior 128 S10D observations.

Both are causal and prior-only.

The rule is monotonic and contains no narrow absolute price/flow band.

## Why this candidate is accepted

More aggressive candidates produced larger fresh improvement, but they worsened Research Discovery.

The accepted rule is the candidate that:

> **improves protected PnL in all 6 chronological development blocks**

while retaining:
- **96.05%** of research executable strong winners overall
- **99.39%** of fresh executable strong winners overall

This follows the post-S10H principle:

> stable modest improvement is preferred over a larger regime-specific improvement.

---

# Full-system comparison

## Research

### Primary V2 before S10J-6B

> 317 selected → 280 executable → 76 executable strong

- protected WR: **34.64%**
- protected PnL: **-$131.62**

### Accepted S10J-6B

> **304 selected → 270 executable → 73 executable strong**

- protected WR: **34.81%**
- protected PnL: **-$121.15**

Improvement:

> **+$10.46**

The rule vetoes 10 executable research trades:
- 3 strong
- 3 severe fallback
- protected PnL of vetoed cohort: **-$10.46**

---

# Fresh development result

## Primary V2 before S10J-6B

> 723 selected → 616 executable → 164 executable strong

- protected WR: 34.58%
- protected PnL: **-$218.66**

## Accepted S10J-6B

> **699 selected → 600 executable → 163 executable strong**

- protected WR: **34.83%**
- protected PnL: **-$182.01**

Improvement:

> **+$36.65**

The rule vetoes 16 executable fresh T+2 trades:
- only **1 strong**
- **9 severe fallback**
- vetoed cohort protected PnL: **-$36.65**

Fresh executable strong retention:

> **163 / 164 = 99.39%**

---

# Six-block stability

## Research Discovery

Primary V2:
> -$108.52

S10J-6B:
> **-$107.76**

Improvement:
> **+$0.76**

## Research Validation

Primary V2:
> +$11.00

S10J-6B:
> **+$11.11**

Improvement:
> **+$0.10**

## Research Reserve

Primary V2:
> -$34.10

S10J-6B:
> **-$24.49**

Improvement:
> **+$9.61**

## Fresh Oct 1

Primary V2:
> -$177.91

S10J-6B:
> **-$156.80**

Improvement:
> **+$21.11**

## Fresh Oct 2

Primary V2:
> +$36.51

S10J-6B:
> **+$45.14**

Improvement:
> **+$8.63**

## Fresh Oct 3

Primary V2:
> -$77.27

S10J-6B:
> **-$70.35**

Improvement:
> **+$6.92**

Result:

> **6 / 6 chronological blocks improve protected PnL.**

This is the primary reason this rule is preferred over more aggressive alternatives.

---

# T+2 lane effect

## Research T+2

Before:
> 94 executable / 27 strong / **-$88.49**

After:
> **84 executable / 24 strong / -$78.03**

Improvement:
> **+$10.46**

## Fresh T+2

Before:
> 192 executable / 58 strong / **-$70.88**

After:
> **176 executable / 57 strong / -$34.23**

Improvement:
> **+$36.65**

Thus S10J-6B cuts approximately half of the fresh T+2 net loss while losing only one fresh executable strong target.

T+2 is materially improved but not yet positive.

---

# Full fresh lane economics after accepted S10J-6B

| Lane | Executable | Strong | Protected PnL |
|---|---:|---:|---:|
| T0 | 181 | 37 | **-$75.99** |
| T+1 | 175 | 51 | **-$66.14** |
| T+2 | 176 | 57 | **-$34.23** |
| T+3 | 68 | 18 | **-$5.65** |
| **Total** | **600** | **163** | **-$182.01** |

The next largest unresolved loss is now:

1. T0: -$75.99
2. T+1: -$66.14
3. T+2: -$34.23
4. T+3: -$5.65

---

# More aggressive challengers

## Economic-safe challenger

Rule:

> `t2_confirm_side_return_pct__lrz64 <= -0.25`  
> AND  
> `f_f_coin_minus_market_30m__lpct64 <= 0.30`

Fresh:
- PnL improvement: **+$58.76**
- total PnL: **-$159.91**
- executable strong retention: **99.39%**

Research:
- improvement: +$4.24
- but Research Discovery worsens by approximately **$4.97**

Therefore it is not accepted as the stable primary.

## Aggressive challenger

Rule:

> `t2_confirm_side_return_pct__lrz64 <= 0`  
> AND  
> `f_f_coin_minus_market_30m__lpct64 <= 0.30`

Fresh:
- improvement: **+$62.23**
- total: **-$156.44**

Research:
- improvement: +$5.58

But:
- two research executable strong winners removed
- two fresh executable strong winners removed
- Research Discovery worsens by approximately **$3.63**

Again, not accepted.

---

# Four-signal scan

OR combinations of two AND clauses were tested.

They did not provide a sufficiently large incremental benefit versus the simpler two-signal candidates.

Given the prior S10G overfit failure:

> **four-signal complexity is rejected.**

---

# Verdict

> **S10J-6B = PASS as a targeted severe-fallback repair.**

The accepted T+2 normalized conjunction:
- improves research PnL
- improves fresh development PnL
- improves all six chronological blocks
- removes 9 fresh severe fallback trades
- sacrifices only 1 fresh executable strong target
- reduces fresh T+2 loss from **-$70.88 to -$34.23**

However:

> full fresh protected PnL remains **-$182.01**

Therefore:

> **overall SHORT profitability still FAILS.**

No runtime or production promotion is authorized.

## Next engineering implication

T+2 is no longer the largest remaining lane problem.

After S10J-6B, priority becomes:

1. **T0 severe-fallback anatomy/repair**
2. residual T+1 severe-fallback repair
3. only revisit T+2 if later evidence justifies it
4. leave T+3 alone initially

Any additional repair using S10H remains development-only and still requires a later unseen sealed validation window.
