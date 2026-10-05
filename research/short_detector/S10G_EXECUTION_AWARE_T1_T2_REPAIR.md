# SHORT-S10G — Execution-Aware T+1/T+2 Lane Repair

Status: **PASS — execution-realistic research frontier / not production authority**

## Objective

Repair the execution-economics failure identified in S10F without touching lanes that were already net-positive.

Frozen before S10G:
- T0 fast lane
- T+3 lane
- V4.3 SHORT-LS4
- BE0.10 on the V4.3 NO_ACTION lane

S10F execution-realistic S10E baseline:

> **331 selected → 290 executable → 78 executable strong WIN → 212 executable non-target**

Protected with V4.3 + BE0.10:

> **-$106.99**

Lane anatomy:
- T0: **+$14.78**
- T+1: **-$89.37**
- T+2: **-$36.45**
- T+3: **+$4.04**

Therefore S10G changes only T+1 and T+2.

## Search hygiene

S10G uses only information available causally at or before the lane decision:
- T0 features
- T+1 features for T+1
- T0/T+1/T+2 information for T+2

Timestamp / infrastructure / latency features are excluded from the modeled feature pool.

Single-feature veto regions are fitted on **Discovery executable trades** using protected V4.3+BE0.10 PnL.

Discovery winner-loss limits:
- T+1: max 1 strong WIN removed
- T+2: max 2 strong WIN removed

A robust research pool was then formed by requiring no executable strong-WIN removal in Validation or Reserve and non-positive veto-cohort protected PnL in all three splits.

Because Validation/Reserve were used to form this robustness pool, this is **not a newly sealed holdout validation**.

Within that robust pool, the accepted combinations below are ranked by Discovery economics.

## Accepted T+1 veto

For a trade assigned to T+1, veto if **ANY** of:

1. `f_new_accel_15_vs_60 in [0.23479833333333333, 0.42964424999999995]`
2. `f_new_volume_over_range in [1.6920917148647434, 2.7757644232664087]`
3. `f_gate_price_drift_pct in [0.07936507936507908, 0.19951230325869762]`

All three inputs are available at T0.

### T+1 before repair

Executable:
- 104
- 13 strong WIN
- 91 non-target
- protected PnL: **-$89.37**

### T+1 veto cohort

Selected veto:
- 75 nominal selections
- 2 nominal strong WIN

Executable veto:
- 65
- **1 executable strong WIN**
- **64 executable non-target**
- protected-positive: 8
- protected PnL: **-$124.62**

### T+1 after repair

> **40 selected → 39 executable → 12 strong WIN + 27 non-target**

Protected:
- 17 positive / 39
- WR: **43.59%**
- PnL: **+$35.25**

Thus T+1 changes from:

> **-$89.37 → +$35.25**

## Accepted T+2 veto

For a trade assigned to T+2, veto if **ANY** of:

1. `t2_confirm_side_return_pct in [0.07608306480486604, 0.09980039920158834]`
2. `f_f_taker_accel_1m in [0.09303476722726256, 0.2024488044201611]`
3. `f_new_gate_price_x_flow_gap in [0.0035063885726661333, 0.0324416175051618]`

The first rule is available at the causal T+2 confirmation point. The remaining two are T0 features.

### T+2 before repair

Executable:
- 77
- 26 strong WIN
- 51 non-target
- protected PnL: **-$36.45**

### T+2 veto cohort

Selected veto:
- 31 nominal selections
- 2 nominal strong WIN

Executable veto:
- 26
- **2 executable strong WIN**
- **24 executable non-target**
- protected-positive: **0 / 26**
- protected PnL: **-$59.36**

### T+2 after repair

> **70 selected → 51 executable → 24 strong WIN + 27 non-target**

Protected:
- 28 positive / 51
- WR: **54.90%**
- PnL: **+$22.91**

Thus T+2 changes from:

> **-$36.45 → +$22.91**

## Full S10G result

### Before — S10F / S10E

> **331 selected → 290 executable**

- nominal strong WIN: 83 / 99
- executable strong WIN: 78 / 99
- executable non-target: 212
- protected-positive: 102
- protected WR: 35.17%
- protected PnL: **-$106.99**
- gross profit: +$209.52
- gross loss: -$316.52

### After S10G

> **225 selected → 199 executable**

- nominal strong WIN: **79 / 99 = 79.80%**
- executable strong WIN: **75 / 99 = 75.76%**
- executable non-target: **124**
- protected-positive: **94**
- protected WR: **47.24%**
- protected PnL: **+$76.98**
- gross profit: +$200.96
- gross loss: **-$123.98**

Delta versus S10F S10E:

- selected: 331 → **225**
- executable: 290 → **199**
- executable non-target: 212 → **124**
- executable strong WIN: 78 → **75**
- protected WR: 35.17% → **47.24%**
- protected PnL: -$106.99 → **+$76.98**
- protected PnL improvement: **+$183.98**
- gross loss reduction: approximately **$192.54**

The vetoed executable cohort is:

> **91 executable → 3 strong WIN + 88 non-target → -$183.98 protected PnL**

Only 8 / 91 vetoed executable trades were protected-positive.

## Strong-WIN cost

Four nominal strong targets are removed:
- AERO — Discovery — T+2 — executable — protected PnL approximately -$0.02
- ALICE — Discovery — T+1 — executable — protected PnL approximately +$0.87
- CHIP — Discovery — T+2 — executable — protected PnL approximately -$0.17
- NIL — Validation — T+1 — **not executable before veto**

Therefore:
- executable strong-WIN retention = **75 / 78 = 96.15%**
- no executable Validation strong WIN is removed
- no executable Reserve strong WIN is removed
- only one removed executable strong target had materially positive protected PnL, and it was below +$1

## Lane economics after repair

| Lane | Executable | Strong | Non-target | Protected WR | Protected PnL |
|---|---:|---:|---:|---:|---:|
| T0 | 80 | 29 | 51 | 43.75% | **+$14.78** |
| T+1 | 39 | 12 | 27 | 43.59% | **+$35.25** |
| T+2 | 51 | 24 | 27 | 54.90% | **+$22.91** |
| T+3 | 29 | 10 | 19 | 48.28% | **+$4.04** |
| **Total** | **199** | **75** | **124** | **47.24%** | **+$76.98** |

All four entry lanes are now net-positive in the research replay.

## Chronological protected economics after repair

### Discovery

> **123 selected → 105 executable**

- 45 executable strong WIN
- 60 executable non-target
- 53 protected-positive
- WR: **50.48%**
- PnL: **+$50.97**

### Validation

> **51 selected → 46 executable**

- 19 executable strong WIN
- 27 executable non-target
- 27 protected-positive
- WR: **58.70%**
- PnL: **+$20.55**

### Reserve

> **51 selected → 48 executable**

- 11 executable strong WIN
- 37 executable non-target
- 14 protected-positive
- WR: **29.17%**
- PnL: **+$5.46**

Thus:

> **Discovery, Validation, and Reserve are all positive after the execution-aware lane repair.**

## Protector contribution

On the 199 executable S10G-kept positions:

Delayed historical-time hold:
- 69 positive
- WR: 34.67%
- PnL: **-$123.04**

V4.3 standalone:
- 98 positive
- WR: 49.25%
- PnL: **-$93.50**

V4.3 + BE0.10:
- 94 positive
- WR: **47.24%**
- PnL: **+$76.98**

The protector still contributes the final loss compression needed for positive economics.

## Verdict

> **SHORT-S10G = PASS as the first positive execution-realistic research operating point.**

Accepted research point:

> **225 selected → 199 executable → 75 executable strong WIN / 99 → 124 executable non-target → +$76.98**

But:

> **NOT production-authorized.**

Reason:
- Validation/Reserve were already observed during prior research;
- S10G uses them as part of a robustness filter;
- therefore a fresh sealed forward/chronological validation is still required before runtime promotion.

No runtime trading changes are authorized by this stage.
