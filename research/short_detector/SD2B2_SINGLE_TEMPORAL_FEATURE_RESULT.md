# SD-2B2 — SHORT Single Temporal Feature Scan

Status: **PARTIAL PASS — Lane 1 T+3 STRONG research candidate; Lane 0 primary candidate fails holdout**

## Frozen scope

Matched research lanes remain unchanged.

### Lane 0
- provisional SHORT_ARCHETYPE_0 WIN vs SHORT_LOSS_CLUSTER_0
- pre-censor D/V/R:
  - 17/82
  - 8/24
  - 5/17

### Lane 1
- provisional SHORT_ARCHETYPE_1 WIN vs SHORT_LOSS_CLUSTER_1
- pre-censor D/V/R:
  - 42/213
  - 19/66
  - 8/90

Causal eligibility:
`primary_label_end_ms > tN_target_ms`

Predictor family:
- **105 temporal predictors per horizon**
- T+1 / T+2 / T+3
- MFE / MAE excluded from predictor ranking

Search:
- one-sided rules only
- every exact Discovery-observed threshold
- both >= and <=
- no bands
- no multi-feature combinations

Total threshold rules evaluated:

> **144,162**

Per-feature frozen rules:

> **597**

All threshold and feature selection used Discovery + Validation only.
Reserve was opened only after the T+1/T+2/T+3 candidate for each lane was frozen.

---

# 1. Lane 0 — primary horizon candidates

## T+1 frozen D/V winner

Rule:

`t1_f_f_market_dispersion_15m >= 0.0718239313908`

Discovery:
- eligible: 85
- winners: 16
- selected: 56
- captured: 15
- precision: **26.8%**
- recall: **93.8%**
- phi: **0.283**
- baseline winner prevalence: 18.8%
- precision lift: **1.42x**

Validation:
- eligible: 29
- winners: 7
- selected: 17
- captured: 6
- precision: **35.3%**
- recall: **85.7%**
- phi: **0.310**
- precision lift: **1.46x**

Reserve:
- eligible: 19
- winners: 5
- selected: **1**
- captured: **0**
- precision: **0%**
- recall: **0%**
- phi: **-0.141**

Verdict:

> **FAIL**

This rule was also the preregistered Lane-0 preferred horizon because it was the earliest horizon meeting the D/V quality floor.

## T+2 frozen D/V winner

Rule:

`t2_f_f_market_dispersion_15m >= 0.0605692985828`

D:
- 43 selected / 12 winners captured
- recall **100%**
- phi **0.349**

V:
- 16 selected / 6 winners captured
- recall **85.7%**
- phi **0.333**

R:
- 4 selected
- **0 winners captured**
- recall **0%**
- phi **-0.308**

Verdict:

> **FAIL**

## T+3 frozen D/V winner

Rule:

`t3_f_f_market_dispersion_15m >= 0.07386309514`

D:
- recall **100%**
- phi **0.389**

V:
- recall **85.7%**
- phi **0.428**

R:
- selected 1
- captured 0
- recall **0%**
- phi **-0.161**

Verdict:

> **FAIL**

### Lane-0 interpretation

The same static-ish market-dispersion family dominated threshold ranking in D/V at all three horizons, then collapsed completely in Reserve.

This is consistent with SD-2A's observed market-dispersion regime shift.

Therefore:

> **Lane 0 has no promotable primary threshold rule from SD-2B2.**

---

# 2. Lane-0 secondary robustness evidence

Although the D/V-selected primary horizon rules fail, several individually frozen feature rules happen to pass the preregistered all-split tier after Reserve is opened.

These are **not allowed to replace the primary D/V-selected rule post hoc**.

## T+2
- 100 per-feature frozen rules
- **6 STRONG**
- **22 PROMISING-or-better**

Examples:

`t2_f_f_structure_reversal_score <= 1.8625058384`
- phi D/V/R: **0.294 / 0.302 / 0.358**
- recall: **100% / 100% / 100%**

`t2_f_f_two_bar_opposite_body <= 0.190789473684`
- phi: **0.283 / 0.397 / 0.410**
- recall: **100% / 100% / 100%**

`t2_delta_f_coin_minus_market_15m >= 0.0320309680839`
- phi: **0.251 / 0.302 / 0.381**
- recall: **66.7% / 42.9% / 75.0%**

## T+3
- 98 per-feature frozen rules
- **7 STRONG**
- **29 PROMISING-or-better**

Examples:

`t3_f_micro_decay_3_vs_prev3 <= 0.277903165662`
- phi: **0.342 / 0.328 / 0.452**
- recall: **66.7% / 42.9% / 50.0%**

`t3_delta_micro_side_ret_3m >= -0.277903165662`
- identical classification behavior

These results confirm that Lane-0 temporal structure is real, but selecting one of these **after** Reserve inspection would violate the stage contract.

They should only inform a fresh preregistered validation stage.

---

# 3. Lane 1 — T+1

Frozen D/V winner:

`t1_f_micro_decay_5_vs_prev5 <= -0.679747412123`

D:
- selected 61
- captured 18 / 38
- precision **29.5%**
- recall **47.4%**
- phi **0.219**

V:
- selected 26
- captured 9 / 18
- precision **34.6%**
- recall **50.0%**
- phi **0.212**

R:
- selected 37
- captured **1 / 6**
- precision **2.7%**
- recall **16.7%**
- phi **-0.133**

Verdict:

> **FAIL**

This was the preregistered earliest preferred Lane-1 horizon based on D/V only.

Reserve rejects it clearly.

---

# 4. Lane 1 — T+2

Frozen D/V winner:

`t2_f_f_two_bar_opposite_body <= 0.0696465696466`

Discovery:
- 115 selected
- 27 / 35 winners captured
- precision **23.5%**
- recall **77.1%**
- phi **0.215**

Validation:
- 36 selected
- 12 / 17 captured
- precision **33.3%**
- recall **70.6%**
- phi **0.250**

Reserve:
- 49 selected
- 5 / 6 captured
- precision **10.2%**
- recall **83.3%**
- phi **0.143**

Verdict:

> **FAIL** under the preregistered PROMISING gate because Reserve phi <0.15.

It is close, but the gate is not relaxed post hoc.

---

# 5. Lane 1 — T+3

Frozen D/V winner:

> `t3_confirm_side_return_pct >= +0.0338983050847%`

This threshold is independently learned from SHORT.
It is **not** the LONG +0.158514% threshold.

## Discovery

- eligible: **181**
- winners: **27**
- selected: **76**
- captured: **23**
- precision: **30.3%**
- recall: **85.2%**
- baseline winner prevalence: **14.9%**
- precision lift: **2.03x**
- phi: **0.366**

## Validation

- eligible: **72**
- winners: **17**
- selected: **22**
- captured: **11**
- precision: **50.0%**
- recall: **64.7%**
- baseline prevalence: **23.6%**
- precision lift: **2.12x**
- phi: **0.412**

## Reserve

- eligible: **78**
- winners: **6**
- selected: **30**
- captured: **5**
- precision: **16.7%**
- recall: **83.3%**
- baseline prevalence: **7.7%**
- precision lift: **2.17x**
- phi: **0.266**

All preregistered STRONG gates pass:

- phi D >= 0.25: PASS
- phi V >= 0.25: PASS
- phi R >= 0.25: PASS
- recall D >=40%: PASS
- recall V >=40%: PASS
- recall R >=40%: PASS

Verdict:

> **STRONG RESEARCH CANDIDATE**

D/V/R phi:
> **0.366 / 0.412 / 0.266**

D/V/R recall:
> **85.2% / 64.7% / 83.3%**

This is the first SHORT temporal threshold in the current research sequence that passes the full preregistered STRONG classification gate.

---

# 6. Is Lane-1 T+3 a one-off?

No.

Among 101 per-feature frozen T+3 Lane-1 rules:

- **2 STRONG**
- **11 PROMISING-or-better**

The second STRONG rule is:

`t3_f_micro_side_ret_3m >= +0.162469536962%`

Phi D/V/R:
- **0.313 / 0.334 / 0.321**

Recall:
- **55.6% / 41.2% / 50.0%**

Reserve precision:
- **30.0%**
- precision lift: **3.90x**

This supports the broader SD-2B1 conclusion that T+3 favorable side-relative price development is a genuine Lane-1 signal family.

However, the official frozen horizon winner remains:

> **T+3 confirm side return >= +0.0338983%**

because it ranked first under the preregistered D/V selection process.

---

# 7. Historical PnL warning

The frozen T+3 Lane-1 rule's **historical original-entry** selected PnL is:

- Discovery: **-$105.74**
- Validation: **-$0.68**
- Reserve: **-$50.84**

This does **not** invalidate the classifier result.

The historical PnL reflects:
- the old original-entry timing;
- old exit behavior;
- no reconstructed delayed T+3 entry;
- no V4.3-style profit protection for the new SHORT lane.

Therefore SD-2B2 is a **classification / confirmation result**, not a profitability proof.

Execution economics must be tested separately.

---

# 8. Contract nuance — preferred horizon

The preregistered "earliest qualified D/V horizon" designation was:

- Lane 0: **T+1**
- Lane 1: **T+1**

Both preferred early rules fail Reserve.

This designation is **not rewritten** after seeing Reserve.

Separately, all T+1/T+2/T+3 horizon candidates were independently frozen before Reserve opened.

Therefore the Lane-1 T+3 STRONG result is a valid pre-frozen horizon test, but it should be treated as a later-horizon research candidate rather than retroactively renaming T+3 as the original preferred horizon.

---

# 9. Final SD-2B2 verdict

## Lane 0
Primary D/V-selected rules:
- T+1: FAIL
- T+2: FAIL
- T+3: FAIL

Status:

> **NO PRIMARY PASS**

Temporal structure exists, but candidate selection is unstable and Lane-0 Reserve support is small.

## Lane 1
- T+1: FAIL
- T+2: FAIL (near-PROMISING, Reserve phi 0.143)
- T+3: **STRONG**

Status:

> **PARTIAL PASS — T+3 SIDE-RETURN CONFIRMATION**

## Overall

> **SD-2B2 = PARTIAL PASS**

First viable SHORT confirmation candidate:

> **Lane 1 / T+3 / confirm_side_return_pct >= +0.0338983%**

It has no live/paper authority yet.

---

# 10. Next stage

The clean next step is **execution-realistic delayed replay** of the frozen Lane-1 T+3 rule before adding complexity.

Questions to answer:
1. what is the first executable market timestamp after T+3?
2. how much MFE remains after delayed entry?
3. how many of the 23 / 11 / 5 captured winners remain economically tradeable?
4. what are delayed-entry PnL, WR, MAE, and adverse slippage?
5. does the rule still add value with a realistic SHORT exit / protection policy?

Lane 0 should not receive a post-hoc threshold promotion without a fresh validation contract.