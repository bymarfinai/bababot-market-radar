# SHORT-SA5C — Conditional Kill Discovery inside B1/B2

Status: **PASS for B2 conditional kill / B1 unresolved / NOT runtime-ready**

## Objective

SA-5C converts the broad SA-5B failure territories into selective negative rules.

Frozen SA-5B families:

1. **B1 — 30M PROXIMITY STALL**
2. **B2 — WEAK PRESSURE / DRIFT STALL**

The task is deliberately different from SA-5B:

> broad family membership is not enough to kill a trade.

SA-5C searches for second-order, pre-T, market-causal conditions that separate BAD from TARGET inside each family.

Constraints:

- no future MFE as live input
- no realized PnL in threshold formation
- no T feature as negative-selector basis
- Research Discovery TARGET quantiles define thresholds
- Research/Fresh transport required
- strong/TARGET combined retention must remain at least 95%
- SA-3 positive T rescue remains a separate layer
- no runtime or paper-trading change

---

# 1. Conditional feature anatomy

## B1

B1 contains:

- BAD: 67
- TARGET: 80

Only two features survive the strict conditional stability screen:

1. **f_f_range_climax_fade_10m — HIGH_BAD**
2. **f_micro_range_contraction_after_impulse — HIGH_BAD**

Interpretation:

> inside the 30m proximity-stall territory, BAD tends to show a stronger climax/fade signature and stronger contraction after the initial impulse.

However, these features overlap too strongly with valid strong/TARGET trades.

No tested B1 conditional rule achieved the required collateral guardrail.

Therefore:

> **B1 conditional kill = FAIL / unresolved.**

No B1 rule is frozen.

---

# 2. B2 conditional anatomy

B2 contains:

- BAD: 33
- TARGET: 46

The strongest stable market-causal conditional dimensions include:

- positioning OI change
- selected taker share
- market dispersion
- breakdown depth
- 30m market selected return
- price-flow divergence
- market aligned fraction
- family balance

Latency, clock-time, and score-state features were explicitly excluded from the frozen candidate basis even where they showed separation.

The desired pattern is not simply "weak movement".

The clean B2 failure pattern is:

> **aggressive selected taker participation + weak broad market confirmation + weak 30m market move + elevated price/flow divergence.**

This is consistent with a crowded/unconfirmed impulse:

> flow looks aggressive, but price and market breadth do not confirm it.

---

# 3. Candidate scan

The conditional scan found many B2 branches with zero TARGET and zero strong hits.

A greedy set-cover based only on classification/transport — not PnL — initially selected two branches:

### C1 — Crowded divergence

3 of 4 conditions at TARGET Q80:

- high positioning OI change
- shallow breakdown depth
- high price-flow divergence
- high market aligned fraction

Classification:

- BAD: 8
- TARGET: 0
- strong: 0
- GRAY: 2

But exact replay validation found one profitable GRAY trade in Research Validation.

C1 removed-cohort PnL:

> **-$2.73**

but Research Validation contribution:

> **+$1.30**

Therefore:

> **C1 is rejected by chronological PnL validation.**

This is an example of why label precision alone is not sufficient.

---

# 4. SA-5C primary — B2 TAKER / DISPERSION / DIVERGENCE kill

The winning B2 branch is intentionally stricter.

All **4 of 4** conditions must be true.

Thresholds are Research Discovery B2 TARGET Q70 / lower-tail Q30 equivalents.

## Frozen conditions

### 1. High selected taker share

> f_micro_selected_taker_share_prev3m >= **0.7522288016**

### 2. Low market dispersion

> f_f_market_dispersion_15m <= **0.0873032933**

### 3. Low 30m market selected return

> f_f_market_selected_ret_30m <= **0.2061286502**

### 4. High price-flow divergence

> f_micro_price_flow_divergence >= **0.0136461045**

All four are required.

Interpretation:

> selected-side taker flow is very aggressive, but the broader market is not dispersing in the same direction, the 30m market move remains weak, and price/flow divergence is elevated.

This is a **crowded but unconfirmed pressure signature**.

---

# 5. Why Q70 is frozen

Q70 is not selected because it has the best PnL.

Percentile selection is based on the BAD/TARGET/strong boundary only.

| Threshold | Selected | BAD | GRAY | TARGET | Strong |
|---|---:|---:|---:|---:|---:|
| Q60 | 23 | 10 | 7 | 6 | 5 |
| Q65 | 17 | 8 | 7 | 2 | 2 |
| **Q70** | **11** | **7** | **4** | **0** | **0** |
| Q75 | 8 | 6 | 2 | 0 | 0 |
| Q80 | 3 | 2 | 1 | 0 | 0 |

So:

> **Q70 is the first tested clean boundary with zero TARGET and zero strong collateral.**

Q75 is retained as a stricter safety comparator.

PnL is evaluated only after this boundary is frozen.

---

# 6. Exact primary cohort

Q70 primary selects:

- **11 trades**
- BAD: **7**
- GRAY: **4**
- TARGET: **0**
- strong: **0**

All 11 are executable in the current SA-3 state.

All 11 are historical losses:

> wins = **0**

Dropped cohort PnL:

> **-$12.5421**

Breakdown:

### BAD-A <0.30%

- 3 trades
- **-$4.0576**

### BAD-B 0.30-0.50%

- 4 trades
- **-$8.1812**

### GRAY 0.50-1.00%

- 4 trades
- **-$0.3033**

### TARGET >=1%

- **0**
- $0

The GRAY collateral is therefore economically negative as well.

---

# 7. Chronological validation

Q70 removes negative PnL in every block where it fires:

| Block | Removed exec | Removed PnL |
|---|---:|---:|
| Research Discovery | 1 | **-$0.0868** |
| Research Validation | 0 | $0 |
| Research Reserve | 2 | **-$2.8082** |
| Fresh Oct 1 | 3 | **-$1.3455** |
| Fresh Oct 2 | 2 | **-$0.1605** |
| Fresh Oct 3 | 3 | **-$8.1412** |

Therefore:

> **5 / 5 active blocks improve.**

Research Validation is untouched.

Source decomposition:

### Research

Removed:

> **-$2.8949**

### Fresh

Removed:

> **-$9.6472**

Both sources improve.

---

# 8. SA-3 rescue interaction

Q70 primary overlap with the existing SA-3 delayed T2/T3 rescue cohort:

> **0 trades**

Therefore the architecture is clean:

> the new negative rule does not fight the existing positive rescue layer.

No re-replay of rescued trades is needed for this candidate because none of the 11 killed trades is currently rescued.

---

# 9. Final combined-system impact

Current SA-3:

- executable: 744
- wins: 284
- WR: **38.17%**
- strong executable: 234
- strong retention: **95.12%**
- TARGET executable: 266
- TARGET retention: **95.34%**
- PnL: **-$67.09**

After SA-5C Q70 primary:

- executable: **733**
- wins: **284**
- WR: **38.74%**
- strong executable: **234**
- strong retention: **95.12%**
- TARGET executable: **266**
- TARGET retention: **95.34%**
- PnL: **-$54.55**

Improvement:

> **+$12.54**

Strong and TARGET retention are unchanged because the primary cohort contains no strong or TARGET trades.

---

# 10. Residual MFE economics after SA-5C

### BAD-A

- 132 -> **129 executable**
- PnL: -$271.04 -> **-$266.98**

### BAD-B

- 102 -> **98 executable**
- PnL: -$232.64 -> **-$224.45**

### GRAY

- 244 -> **240 executable**
- PnL: -$127.63 -> **-$127.33**

### TARGET

Unchanged:

- **266 executable**
- **+$564.21**

The detector is still negative overall.

SA-5C is not a profitability solution by itself.

---

# 11. Q75 safety comparator

Q75 keeps the same zero-TARGET / zero-strong property.

It removes:

- 8 executable
- 6 BAD
- 2 GRAY
- wins: 0
- PnL: **-$12.2533**

Combined result:

> **-$54.84**

This is only about $0.29 worse than Q70 while using a stricter threshold.

Therefore Q75 is a useful conservative comparator.

However Q70 remains the research primary because:

- it is the first clean label boundary;
- it captures one additional BAD and two additional negative GRAY;
- all additional Q70-vs-Q75 trades are still losses;
- no strong/TARGET collateral appears.

---

# 12. What SA-5C did not solve

## B1 remains unresolved

No safe B1 kill was found.

Do not relax B1 thresholds globally.

## B2 still has residual BAD

Q70 removes:

> **7 / 33 B2 BAD = 21.2%**

So most B2 BAD remain.

The clean rule is high precision but deliberately narrow.

## Overall system remains negative

> **-$54.55**

Residual BAD-A/B remains the main negative mass.

---

# SA-5C verdict

> **PASS as a research-only B2 conditional kill candidate.**

Frozen primary:

> **B2 + all-four Q70 Taker / Dispersion / Market-Return / Price-Flow Divergence rule**

Reasons:

- 0 TARGET collateral
- 0 strong collateral
- no overlap with SA-3 rescue
- 11/11 exact trades are losses
- Research and Fresh both improve
- 5/5 active chronological blocks improve
- PnL improves **-$67.09 -> -$54.55**
- WR improves **38.17% -> 38.74%**
- strong/TARGET retention remains unchanged above 95%

But:

> **NOT runtime-ready.**

All known cohorts have now influenced this research path, and the B2 Research Discovery TARGET threshold base is small.

An unseen/sealed cohort is still required before promotion.

---

# Recommended next stage

The next logical stage is:

> **SA-5D — Residual Recomposition after SA-5C**

It should recompute the full residual failure anatomy after Q70 and determine whether the next highest-value problem is:

1. unresolved B1,
2. remaining B2 BAD,
3. SA-4 one-condition-short A1/A2/A3 population,
4. or GRAY fallback economics.

Do not automatically add another B2 branch merely to increase coverage.

No runtime promotion is authorized by SA-5C.