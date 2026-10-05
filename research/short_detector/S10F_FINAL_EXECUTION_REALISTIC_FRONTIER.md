# SHORT-S10F — Final Efficient Frontier & Execution-Realistic Validation

Status: **COMPLETE — DIAGNOSTIC PASS / PRODUCTION PROMOTION FAIL**

## Objective

Compare the frozen SHORT research frontier under execution-realistic entry timing, without creating or tuning a new detector rule.

Candidates:

1. **S10C**
   - 329 selected
   - 70 / 99 nominal strong WIN

2. **S10D**
   - 364 selected
   - 85 / 99 nominal strong WIN

3. **S10E accepted**
   - 331 selected
   - 83 / 99 nominal strong WIN
   - T0 overheat-pressure veto

4. **S10E maximum-prune**
   - 310 selected
   - 81 / 99 nominal strong WIN
   - OI 30m veto

Frozen protector:

> **V4.3 SHORT-LS4 + BE0.10 on the V4.3 NO_ACTION lane**

No new detector threshold was fitted in S10F.

## Execution contract

The replay follows the existing SD-2B4 delayed-entry contract.

### Temporal entry

For T+1 / T+2 / T+3 selections:

> entry = open of the first Binance USD-M Futures 1-minute bar strictly after the qualifying temporal target timestamp.

If the historical position has already closed before that entry minute:

> `NO_EXECUTABLE_ENTRY`

### T0 fast lane

S10D-derived T0 fast-entry signals are available at the original decision time.

Therefore:

> T0 entry uses the original historical paper entry fill.

When a routed-Lane-1 trade is both a T0-fast candidate and a later temporal candidate, the T0 lane wins because it is available first.

This is the intended S10D behavior.

### Exit replay

For every executable reconstructed position:
- $500 notional metadata unless position metadata specifies otherwise
- frozen fee / slippage metadata
- exact Binance USD-M aggTrade path after reconstructed entry
- V4.3 5-second protector sampling
- BE0.10 only if V4.3 remains NO_ACTION
- original historical final-close time is the fallback boundary

## Market-data integrity

- 256 Binance 1m kline symbol-date pairs
- **0 kline errors**
- 273 Binance aggTrade symbol-date pairs
- **0 aggTrade errors**

## Benchmark reproduction

S10F was cross-checked against the authoritative SD-2B4 replay.

Among 20 directly comparable T+3 positions with identical delayed-entry timestamps:

> **20 / 20 V4.3 PnL values reproduce exactly to floating-point precision.**

Therefore the execution-replay engine is consistent with the existing frozen benchmark.

---

# Final execution-realistic frontier

## S10C

Selected:
> **329**

Executable:
> **283**

No executable entry:
> 46, including 6 strong WIN

Executable strong WIN:
> **64 / 99**

Entry mix:
- T+1: 161 selected
- T+2: 133
- T+3: 35

### Economics

Delayed hold:
> **-$525.39**

V4.3:
> **-$468.77**

V4.3 + BE0.10:
> **-$236.50**

Protected:
- 86 positive / 283
- WR: 30.39%

Chronological protected PnL:
- Discovery: **-$176.56**
- Validation: **-$5.17**
- Reserve: **-$54.76**

---

## S10D

Selected:
> **364**

Executable:
> **320**

No executable entry:
> 44, including 5 strong WIN

Executable strong WIN:
> **80 / 99**

Entry mix:
- T0: 83
- T+1: 125
- T+2: 119
- T+3: 37

### Economics

Delayed hold:
> **-$498.85**

V4.3:
> **-$457.47**

V4.3 + BE0.10:
> **-$180.54**

Protected:
- 104 positive / 320
- WR: 32.50%

Chronological protected PnL:
- Discovery: **-$143.92**
- Validation: **+$1.11**
- Reserve: **-$37.73**

---

## S10E accepted

Selected:
> **331**

Executable:
> **290**

No executable entry:
> 41, including 5 strong WIN

Nominal strong WIN:
> **83 / 99 = 83.84%**

Executable strong WIN:
> **78 / 99 = 78.79%**

Executable non-target:
> 212

Entry mix:
- T0: 80
- T+1: 115
- T+2: 101
- T+3: 35

### Economics

Delayed hold:
> **-$395.27**

V4.3:
> **-$354.16**

V4.3 + BE0.10:
> **-$106.99**

Protected:
- 102 positive / 290
- WR: **35.17%**
- gross loss: **-$316.52**

Chronological protected PnL:
- Discovery: **-$82.04**
- Validation: **+$6.60**
- Reserve: **-$31.55**

This is the **best absolute execution-realistic total PnL** among the four frozen candidates.

However:

> it remains negative and therefore does not pass production promotion.

### Original-entry vs execution-realistic

Prior original-entry protected replay:

> **+$74.47**

Execution-realistic:

> **-$106.99**

Deterioration:

> **-$181.46**

Therefore the original-entry result materially overstated deployable economics.

---

## Maximum-prune alternative

Selected:
> **310**

Executable:
> **268**

No executable entry:
> 42, including 5 strong WIN

Nominal strong WIN:
> **81 / 99**

Executable strong WIN:
> **76 / 99**

Executable non-target:
> 192

Entry mix:
- T0: 70
- T+1: 108
- T+2: 101
- T+3: 31

### Economics

Delayed hold:
> **-$353.52**

V4.3:
> **-$337.69**

V4.3 + BE0.10:
> **-$111.67**

Protected:
- 92 positive / 268
- WR: 34.33%

Chronological protected PnL:
- Discovery: **-$98.49**
- Validation: **+$1.56**
- Reserve: **-$14.74**

Maximum-prune has the best Reserve economics, but its full PnL is slightly worse than S10E accepted.

---

# Comparative table

| Candidate | Selected | Executable | Exec strong / 99 | Exec non-target | Protected WR | Protected PnL |
|---|---:|---:|---:|---:|---:|---:|
| S10C | 329 | 283 | 64 | 219 | 30.39% | **-$236.50** |
| S10D | 364 | 320 | **80** | 240 | 32.50% | **-$180.54** |
| **S10E** | **331** | **290** | **78** | **212** | **35.17%** | **-$106.99** |
| Max-prune | 310 | 268 | 76 | **192** | 34.33% | **-$111.67** |

Research-relative winner:

> **S10E accepted**

Production verdict:

> **FAIL — no frozen candidate is profitable after execution-realistic entry reconstruction.**

---

# Root cause

The strong-winner opportunity itself survives delayed entry.

For S10E executable positions:

## Strong winners

78 executable strong winners:
- 69 protected-positive
- WR: **88.46%**
- protected PnL: **+$155.75**

## Non-targets

212 executable non-targets:
- 33 protected-positive
- protected PnL: **-$262.74**

Thus:

> the protector is not failing on strong winners.

The problem remains false-positive economics after realistic temporal entry.

## Entry-lane anatomy — S10E

### T0

80 executable:
- 29 strong
- total protected PnL: **+$14.78**

Strong:
- +$46.46

Non-target:
- -$31.67

### T+1

104 executable:
- 13 strong
- total protected PnL: **-$89.37**

Strong:
- **+$41.95**

Non-target:
- **-$131.32**

### T+2

77 executable:
- 26 strong
- total protected PnL: **-$36.45**

Strong:
- **+$44.80**

Non-target:
- **-$81.24**

### T+3

29 executable:
- 10 strong
- total protected PnL: **+$4.04**

Strong:
- +$22.54

Non-target:
- -$18.51

Therefore:

> **T0 and T+3 are already net positive.**

The execution-economics failure is concentrated in:

> **T+1 and T+2 early temporal recovery lanes.**

Especially T+1:
- only 13 strong among 104 executable entries
- 91 executable non-targets
- non-target protected loss -$131.32

T+2 has materially stronger target density, but non-target loss remains too large.

---

# No-executable strong winners

S10E retains five nominal strong winners that cannot be executed under the frozen delayed-entry proxy:

- 0G — Reserve — T+3
- B2 — Validation — T+2
- MOVR — Discovery — T+2
- NIL — Validation — T+1
- PTB — Validation — T+2

All had already historically closed before the reconstructed delayed entry minute.

S10D's T0 fast lane successfully makes ONDO executable; this is why S10D has 5 strong no-exec trades versus S10C's 6.

---

# Protector conclusion

V4.3 + BE0.10 still adds substantial economic value after realistic entry.

For S10E:

> delayed hold: **-$395.27**  
> V4.3 + BE0.10: **-$106.99**

Improvement:

> **+$288.28**

Therefore:

> **do not retune Profit Protector first.**

The remaining primary bottleneck is entry/selection quality in the T+1/T+2 recovery lanes.

---

# S10F verdict

> **S10F = COMPLETE.**

Research operating ranking:
1. **S10E accepted** — best full execution-realistic PnL
2. Max-prune — best Reserve, slightly worse full PnL
3. S10D
4. S10C

But:

> **NONE PASS production profitability.**

No runtime detector changes are authorized.

## Recommended next stage

Proceed to an execution-aware temporal-lane repair stage focused only on:

> **T+1 and T+2**

while freezing:
- T0 fast lane
- T+3 lane
- V4.3 + BE0.10 protector

Objective:
- preserve most of the T+1/T+2 strong winners;
- aggressively remove their non-targets;
- fit only on Discovery;
- validate on Validation and Reserve;
- judge using reconstructed executable-entry PnL, not original-entry historical PnL.

The new research target is no longer generic winner recovery.

It is:

> **make T+1/T+2 economically positive after executable entry.**
