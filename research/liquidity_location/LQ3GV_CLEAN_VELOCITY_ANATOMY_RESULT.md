# LQ-3G-V — Clean Velocity Anatomy

Status: **PASS DIAGNOSIS / POST-ENTRY VELOCITY STRONG / PRE-ENTRY VELOCITY FAIL**

Version: `lq3gv-clean-velocity-anatomy-v1`

## Objective

After LQ-3F corrected the historical MFE labels, the clean OPEN_LANE universe contains:

- total: **209**
- Correct Runner: **45**
- Recovered Drawdown: **15**
- true RIGHT_THEN_FAILURE: **34**
- Stall / No Edge: **44**
- True Wrong Direction: **71**
- realized winners: **63**
- realized WR: **30.14%**

The key question for LQ-3G-V is:

> Is the difference between winners and failures primarily a difference in **speed / velocity / recovery dynamics** rather than static snapshot features?

The stage measures raw Binance Vision aggTrades at:

- T+5s
- T+15s
- T+30s
- T+60s
- T+120s

and separately rebuilds **pre-entry velocity** from T-120s to T0.

No production authority is changed.

---

# 1. Velocity is materially stronger than static entry features

Best static entry feature from LQ-3F:

> best AUC ≈ **0.593**

Best causal post-entry velocity feature:

> `ret_120s` / `v_0_120s_pps`

AUC:

> **0.782**

This is a large jump in discrimination.

Median T+120 return:

- winner: **+0.142%**
- loser: **-0.096%**

Equivalent net velocity:

- winner: **+0.00118 percentage-points/sec**
- loser: **-0.00080 percentage-points/sec**

So the main distinction is not a subtle static setup difference.

It is increasingly:

> **does the trade continue / recover after entry, or does it decay?**

---

# 2. Winner vs TRUE_WRONG separates very early

Velocity is especially strong against **TRUE_WRONG_DIRECTION**.

Winner vs TRUE_WRONG AUC:

| Horizon | AUC |
|---|---:|
| T+5s | **0.766** |
| T+15s | **0.803** |
| T+30s | **0.807** |
| T+60s | **0.854** |
| T+120s | **0.915** |

Examples:

### T+15s

Median winner return:

> **+0.0469%**

Median TRUE_WRONG return:

> **-0.1560%**

### T+30s

Median winner return:

> **+0.0214%**

Median TRUE_WRONG return:

> **-0.2199%**

### T+60s

Median winner return:

> **+0.0370%**

Median TRUE_WRONG return:

> **-0.2808%**

This means:

> **TRUE_WRONG is often visible as adverse speed very early.**

This is far stronger than the static entry snapshot.

---

# 3. Recovery quality also matters

The user's recovery-speed hypothesis is supported, but with an important nuance.

## Winner vs TRUE_WRONG

Recovery efficiency AUC:

- T+60s: **0.826**
- T+120s: **0.922**

Median T+120 recovery efficiency:

- winner: **1.635**
- TRUE_WRONG: **0.266**

Meaning:

> winners recover materially more of their local drawdown, while TRUE_WRONG tends to stay damaged.

## RECOVERED_DRAWDOWN vs TRUE_WRONG

Useful recovery features:

- recovery speed to zero at 15s: AUC **0.740**
- recovery efficiency at 60s: AUC **0.754**
- recovery efficiency at 120s: AUC **0.834**

So the difference is not simply:

> "both fell, but one had smaller MAE."

It is also:

> **how quickly and how completely the trade repairs the adverse move.**

---

# 4. Early toxic warning

Adverse speed alone is useful, but it harms too many winners if used as a blind hard cut.

Example:

> T+15 return <= -0.10%

flags a high-loss group, but still catches too many eventual winners.

Combining adverse movement with poor recovery improves precision.

## Candidate A — T+15 toxic

```
ret_15s <= -0.20%
AND recovery_efficiency_15s <= 0.50
```

Result:

- flagged: **34**
- final losers: **30**
- loss precision: **88.2%**
- TRUE_WRONG: **27**
- RTF: 3
- Correct Runner harmed: **1**
- Recovered Drawdown harmed: **3**

## Candidate B — T+30 toxic

```
ret_30s <= -0.20%
AND recovery_efficiency_30s <= 0.50
```

Result:

- flagged: **39**
- final losers: **35**
- loss precision: **89.7%**
- TRUE_WRONG: **30**
- Stall: 2
- RTF: 3
- Correct Runner harmed: **0**
- Recovered Drawdown harmed: **4**

This is promising as a **loss-protection warning**, but not production-ready as a hard close because it still sacrifices genuine Recovered winners.

---

# 5. Important causal correction: not every trade survives to later horizons

Historical position survival:

| Horizon | Still open |
|---|---:|
| 5s | **209 / 209** |
| 15s | **200 / 209** |
| 30s | **180 / 209** |
| 60s | **164 / 209** |
| 120s | **129 / 209** |

Therefore T+60/T+120 velocity cannot be honestly described as a universal entry predictor.

It is a:

> **post-entry state classifier for trades still alive at that horizon.**

The velocity features were rebuilt so T+N values are only present when the position is actually still open at T+N.

This removes last-price carry-forward / survivor leakage.

---

# 6. Strongest simple post-entry continuation pattern

A deliberately rounded, non-fine-tuned rule was tested:

```
alive at T+120
AND return at T+60 >= -0.02%
AND velocity from T+60 to T+120 > 0
```

Interpretation:

> the trade was not materially broken after one minute, and then **re-accelerated upward during minute two**.

Named:

> **C1_SECOND_MINUTE_REACCELERATION**

## Fair baseline: trades alive at T+120

| Split | Alive | Wins | WR |
|---|---:|---:|---:|
| TRAIN | 75 | 35 | **46.67%** |
| VALIDATION | 30 | 10 | **33.33%** |
| RESERVE | 24 | 10 | **41.67%** |
| ALL | **129** | **55** | **42.64%** |

## C1 pass

| Split | N | Wins | WR |
|---|---:|---:|---:|
| TRAIN | 20 | 16 | **80.00%** |
| VALIDATION | 7 | 5 | **71.43%** |
| RESERVE | 6 | 4 | **66.67%** |
| ALL | **33** | **25** | **75.76%** |

Class mix of the 33 pass trades:

- Correct Runner: **21**
- Recovered Drawdown: **4**
- true RTF: **8**
- TRUE_WRONG: **0**
- STALL: **0**

This is one of the clearest findings in the research so far:

> **no clean TRUE_WRONG and no STALL survive this simple second-minute re-acceleration state.**

The remaining failures are genuine RTF, not bad-direction / no-edge entries.

---

# 7. But C1 is NOT a delayed entry signal

A fresh-entry replay was run.

Contract:

- no position at T0;
- wait until T+120;
- if C1 passes, enter fresh $500 LONG at the first aggTrade after T+120;
- apply configured fee/slippage;
- exit at the same historical close.

Result:

| Split | N | Wins | WR | PnL |
|---|---:|---:|---:|---:|
| TRAIN | 20 | 11 | **55.00%** | +$9.68 |
| VALIDATION | 7 | 2 | **28.57%** | -$1.69 |
| RESERVE | 6 | 2 | **33.33%** | -$11.79 |
| ALL | **33** | **15** | **45.45%** | **-$3.81** |

Therefore:

> **waiting 120 seconds and then buying is chasing.**

The 75.76% figure is a state-classification result on positions already entered earlier.

It must not be promoted as a fresh-entry WR.

---

# 8. C1 is also NOT a universal hard-cut rule

A second replay tested:

- keep historical closes for positions that close before T+120;
- if alive at T+120 and C1 passes: KEEP;
- if alive at T+120 and C1 fails: CLOSE at T+120.

Result:

| System | WR | PnL |
|---|---:|---:|
| Historical | **30.14%** | **-$126.42** |
| Cut every non-C1 survivor | **23.44%** | **-$214.03** |

The hard-cut policy harmed:

> **30 historical future winners**

among the T+120 cuts.

Therefore:

> C1 is **not** permission to close every non-pass trade.

Best interpretation:

> **C1 = strong KEEP / SCALE / relaxed-protection permission**

not:

> delayed-entry permission

and not:

> universal CUT permission.

---

# 9. Pre-entry velocity was tested separately

To answer whether speed could solve admission **before entering**, Binance Vision aggTrades were reconstructed from:

> **T-120s to T0**

for the same 209 clean OPEN_LANE trades.

Features included:

- 5/15/30/60/120s approach velocity;
- segment velocity;
- acceleration into entry;
- recent/medium speed ratios;
- range;
- velocity-adjusted ETA to 5m/15m/nearest supply.

## Result

Best pre-entry velocity/location-speed feature:

> `pre_eta_15m_supply_distance_pct_30s`

AUC:

> **0.610**

Best pure segment velocity:

> `pre_seg_v_30_15s_pps`

AUC:

> **0.585**

Stable two-feature rules reaching >=60% in TRAIN + Validation + Reserve:

> **0**

Therefore:

> **pre-entry velocity does not solve the admission problem.**

The useful speed information emerges mainly **after the trade starts interacting with the market**, not in the final 5–120 seconds leading into entry.

---

# 10. What speed is actually telling us

The data supports a three-state interpretation.

## A. Fast adverse + weak recovery

Typical of:

> TRUE_WRONG / toxic path

Detected from 5–30s onward.

## B. Damage but strong recovery

Typical of:

> genuine recovered trade

Recovery speed/efficiency is materially stronger than TRUE_WRONG.

## C. Survives first minute + re-accelerates in second minute

Typical of:

> Correct Runner / genuine continuation

C1 isolates this state very strongly.

## D. Looks directionally real but later fails

Remaining failures inside C1 are:

> true RTF

So even velocity does not fully solve RTF.

---

# Final LQ-3G-V verdict

## The user's velocity hypothesis

**SUPPORTED — but mostly post-entry.**

Static entry snapshot:

> weak separation

Pre-entry velocity:

> weak-to-moderate separation, no stable 60% rule

Post-entry adverse/recovery/continuation velocity:

> **strong separation**

especially against TRUE_WRONG.

## Strongest use cases

1. **Early toxic warning**
   - 15–30s
   - adverse speed + poor recovery

2. **Recovery-state identification**
   - 15–120s
   - recovery efficiency / recovery speed

3. **Continuation KEEP/SCALE permission**
   - 60–120s
   - no material first-minute damage + positive second-minute velocity

## What NOT to do

Do not:

- delay all entries to T+120;
- cut every non-C1 trade at T+120;
- treat post-entry velocity WR as if it were an entry WR;
- deploy these rules to order authority yet.

---

# Recommended next stage

**LQ-3G-V2 — Velocity State Router Replay**

Research-only state machine:

```
ENTRY
  |
  +-- T+15/T+30: fast adverse + weak recovery
  |       -> EARLY_TOXIC warning
  |
  +-- unresolved
  |       -> NORMAL protection
  |
  +-- T+120: first minute intact + second-minute reacceleration
          -> KEEP / SCALE / runner permission
```

The next replay should test **different actions per state** rather than binary KEEP/CUT:

- EARLY_TOXIC:
  - early reduce / tighter loss protector
- NORMAL:
  - leave current lifecycle unchanged
- C1 continuation:
  - preserve runner / relax premature protection / optionally scale

The key is:

> velocity is useful for **state routing**, not as a replacement for the entry detector.

Production trading authority remains unchanged.