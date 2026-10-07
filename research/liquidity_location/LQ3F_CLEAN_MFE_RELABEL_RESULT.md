# LQ-3F — Clean MFE Relabel + OPEN_LANE Rebuild

Status: **COMPLETE — LEGACY RTF THESIS INVALIDATED / TARGET-60 REQUIRES BETTER ADMISSION**

Version: `lq3f-clean-open-lane-rebuild-v1`

## Why LQ-3F exists

LQ-3E concluded that RIGHT_THEN_FAILURE (RTF) appeared to be the dominant obstacle after OPEN_LANE admission.

During the requested sub-minute exact replay, Binance Vision aggTrades exposed a major inconsistency:

- GOOD trades had raw post-entry MFE that matched the frozen historical MFE almost exactly;
- many legacy RTF trades did not.

Example:

`CYBERUSDT`

- position lifetime: ~21 seconds
- actual price path during position: roughly flat/down
- raw post-entry MFE: about **+0.07%**
- stored legacy lifecycle MFE: **+7.16%**
- stored MAE: **-2.55%**
- historical label: RIGHT_THEN_FAILURE

This cannot be a real profit giveback.

Git history confirms the cause.

Commit:

> `76ba35f` — **Fix Stage12 MFE entry boundary for fast and thesis paths**

dated **4 October 2026** fixed the exact issue: rolling 1m/5m candle extrema that occurred before position entry could previously feed position MFE/MAE.

A later clean-MFE rebuild was frozen in:

> `84e2f65` — PP V4 Stage1J clean MFE entry boundary

Therefore LQ-3F rebuilds the OPEN_LANE research universe from raw post-entry traded prices.

No production authority is changed.

---

## Clean-label contract

Universe:

> LQ-3C OPEN_LANE = **209 LONG trades**

Source:

> Binance Vision USD-M daily aggTrades

For each trade:

- only prices with timestamp >= `opened_at_ms` and <= `closed_at_ms` are eligible;
- entry price is the zero-excursion baseline;
- no pre-entry candle high/low is allowed;
- exact post-entry MFE/MAE are reconstructed from traded prices.

Frozen WD-1 taxonomy thresholds are reused:

- early adverse: **-0.35%**
- wrong-direction MFE ceiling: **0.35%**
- directionally valid MFE: **0.50%**
- runner MFE: **1.00%**
- early window: **30 minutes**

Coverage:

- **209 / 209**
- archive errors: **0**

---

# 1. Legacy labels were materially contaminated

### Legacy class mix

| Class | N |
|---|---:|
| Correct Runner | 19 |
| Recovered Drawdown | 44 |
| RIGHT_THEN_FAILURE | **76** |
| Stall / No Edge | 5 |
| True Wrong Direction | 65 |

### Clean class mix

| Class | N |
|---|---:|
| Correct Runner | **45** |
| Recovered Drawdown | 15 |
| RIGHT_THEN_FAILURE | **34** |
| Stall / No Edge | **44** |
| True Wrong Direction | **71** |

Changed labels:

> **88 / 209 = 42.1%**

The largest corrections were:

- **26** legacy RTF -> STALL_NO_EDGE
- **16** legacy RTF -> TRUE_WRONG_DIRECTION
- **29** RECOVERED_DRAWDOWN -> CORRECT_RUNNER
- **12** TRUE_WRONG_DIRECTION -> STALL_NO_EDGE

Only:

> **34 / 76 legacy RTF**

remain true RTF under clean post-entry price paths.

This is a major correction.

---

# 2. OPEN_LANE location effect still exists as realized outcome context

Actual historical win rate does not depend on the MFE label, so the realized OPEN_LANE baseline remains:

- N = **209**
- realized winners = **63**
- WR = **30.14%**

Chronological:

| Split | N | Wins | WR |
|---|---:|---:|---:|
| TRAIN | 123 | 39 | **31.71%** |
| VALIDATION | 53 | 13 | **24.53%** |
| RESERVE | 33 | 11 | **33.33%** |
| ALL | 209 | 63 | **30.14%** |

So LQ-3C's broad location conclusion remains useful:

> OPEN_LANE is a healthier market-location context than its complement.

But it is **not** a high-WR entry rule.

---

# 3. LQ-3D admission conclusion does not survive clean relabeling

The old LQ-3D filter was:

```
OPEN_LANE
AND consecutive selected bars <= 2
AND gate adjusted drift <= 0.06782%
```

It selects the same 76 trades.

Actual outcome is unchanged:

- N = **76**
- wins = **28**
- WR = **36.84%**

But clean composition is now:

- clean GOOD = **26**
- clean RTF = **12**
- clean BAD / STALL = **38**

Previously the same 76 trades were interpreted as:

- GOOD = 28
- RTF = 38
- BAD = 10

That interpretation is invalid.

The old claim that the filter strongly separated GOOD from BAD was largely driven by contaminated MFE labels.

---

# 4. Profit Protector cannot mathematically solve the target

This is now the most important conclusion.

## Full OPEN_LANE

Existing realized winners:

> **63**

Clean true RTF:

> **34**

Even under an impossible perfect PP assumption:

- rescue every 34/34 RTF;
- harm zero existing winners;
- convert every rescued RTF into a positive final trade;

maximum winners:

> 63 + 34 = **97**

Maximum WR:

> **97 / 209 = 46.41%**

So:

> **OPEN_LANE + perfect RTF rescue still cannot reach 60%.**

## Old LQ-3D 76-trade filter

Existing winners:

> **28**

Clean true RTF:

> **12**

Perfect rescue upper bound:

> 28 + 12 = **40 winners**

Maximum WR:

> **40 / 76 = 52.63%**

Again:

> **60% is mathematically impossible even with perfect PP.**

Therefore the earlier LQ-3E framing:

> "we mainly need to convert RTF"

is superseded.

The system needs to reject substantially more true wrong-direction / no-edge entries before profit protection becomes the dominant optimization.

---

# 5. Re-run entry-time winner separation on clean ground truth

LQ-3F re-ran the causal entry-time feature scan using:

> actual realized winner vs actual non-winner

rather than legacy GOOD/BAD labels.

Best univariate feature:

> `f_gate_positioning_oi_change_pct`

oriented AUC:

> **0.5929**

Other features are mostly around:

> **0.52–0.55 AUC**

Examples:

- context taker share: ~0.548
- selected slope5 norm: ~0.545
- selected taker share 3m: ~0.544
- reversal pressure: ~0.537
- gate side return 3m: ~0.533

This is weak discrimination.

---

# 6. Two-feature admission search

Thresholds were discovered on TRAIN only.

Minimum TRAIN coverage was enforced.

Validation and Reserve were not used to select thresholds.

Result:

> **stable >=60% rules across TRAIN + VALIDATION + RESERVE: 0**

Best transport-oriented pair had approximately:

- TRAIN WR: **43.75%**
- Validation WR: **44.44%**
- Reserve WR: **50.00%**

No pair comes close to a stable 60% target.

Some tiny Reserve subsets reach >60%, but they collapse in TRAIN/Validation and are rejected.

Therefore:

> the current entry feature family does not contain a simple stable separator capable of producing 60% WR.

---

# 7. Exact sub-minute PP replay discovery

LQ-3F initially ran exact Binance Vision aggTrade replay for the legacy 76-trade cohort.

That replay produced much lower RTF rescue than the LQ-3E theoretical expectation.

This discrepancy was the diagnostic that exposed the label bug.

Example across legacy RTF:

- frozen legacy median MFE: ~**0.664%**
- raw post-entry median MFE: ~**0.238%**
- legacy RTF reaching actual raw MFE >=0.50%: only **12 / 38** in the old 76-trade filter

Therefore the legacy PP replay is not used as the final policy result.

The correct decision is to rebuild labels first, which this stage does.

---

# 8. Runtime status

The production runtime already contains the entry-boundary fix.

Key commits:

- `76ba35f` — Stage12 MFE entry-boundary fix
- `84e2f65` — clean MFE rebuild + runtime freeze

Clean runtime boundary:

> `1791088148534`

The Stage1J deployment recorded:

- zero open positions crossing the boundary;
- lifecycle version `stage12-v3.1-entry-boundary`;
- post-deploy boundary probe PASS.

Therefore this LQ-3F finding is primarily a **historical research-label correction**.

It does not imply current live MFE tracking is still using the broken boundary.

---

# Final verdict

## OPEN_LANE

**KEEP as market-location context.**

It improves opportunity quality versus the broad complement, but is not enough for the target WR.

## Old LQ-3D admission rule

**DO NOT PROMOTE.**

Its strong GOOD-vs-BAD interpretation does not survive clean relabeling.

## LQ-3E PP-only route to 60%

**INVALIDATED.**

Perfect true-RTF rescue cannot mathematically reach 60%.

## Profit protection

Still important for realized PnL capture after a genuinely good admission.

But it is now clearly a downstream optimization, not the main solution to current WR.

## Main bottleneck

> **Admission / signal quality.**

The current OPEN_LANE universe still contains too many:

- TRUE_WRONG_DIRECTION
- STALL_NO_EDGE

and current entry-time features do not separate winners strongly enough.

---

# Recommended next stage

The next research stage should stop tuning PP for this cohort.

Recommended:

> **LQ-3G — Clean Failure Isolation / Admission Rebuild**

Use the clean 209 OPEN_LANE universe and explicitly compare:

1. realized winners;
2. TRUE_WRONG_DIRECTION;
3. STALL_NO_EDGE;
4. true RTF separately.

Expand beyond the current feature family into:

- detector route: FLOW_ALIGNED vs COUNTERFLOW;
- Stage11C family pattern;
- signal score / score edge;
- ignition / expansion state;
- entry latency;
- route-specific temporal confirmation;
- local supply/demand geometry;
- market-relative acceleration;
- route-specific flow structure.

Goal:

> remove true wrong-direction + no-edge trades **before entry** while preserving enough winners.

Only after that admission layer materially improves should PP optimization resume.

Production trading authority remains unchanged.