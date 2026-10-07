# LQ-3G-V3 — Velocity Action Replay

Status: **COMPLETE — MANAGEMENT EDGE CONFIRMED / DELAYED ENTRY REJECTED / PRODUCTION HOLD**

Version: `lq3gv3-velocity-action-replay-v1`

## Objective

LQ-3G-V2 found a strong post-entry state transition:

- T+60 EARLY60 confirmation;
- then T+120 STRONG continuation vs velocity decay.

V3 converts those states into executable replay actions using:

- the original position entry;
- Binance Vision aggTrades;
- actual position fee/slippage settings;
- first traded price at/after the action checkpoint.

No production authority is changed.

---

## Critical eligibility correction

A T+120 state is only valid if the position is still open at T+120.

Across the 209 clean OPEN_LANE trades:

- alive at T+60: **164**
- alive at T+120: **129**
- EARLY60 confirm: **40**
- EARLY60 still alive at T+120: **34**
- EARLY60 closed before T+120: **6**
- STRONG120 confirm: **31**

Therefore the original V2 label:

> EARLY60_ONLY_DECAY = 16

contains six trades that never actually survived to T+120.

Those six are not actionable T+120 decay trades.

The valid executable DECAY120 population is:

> **10 trades**

Contract:

```
EARLY60 = true
AND position alive at T+120
AND STRONG120 = false
```

---

# 1. Historical baseline

Clean OPEN_LANE universe:

| Split | N | Wins | WR | PnL |
|---|---:|---:|---:|---:|
| TRAIN | 123 | 39 | 31.71% | +$1.51 |
| VALIDATION | 53 | 13 | 24.53% | -$89.06 |
| RESERVE | 33 | 11 | 33.33% | -$38.88 |
| ALL | **209** | **63** | **30.14%** | **-$126.42** |

---

# 2. Action A — Close every valid DECAY120 at T+120

Execution:

- original entry unchanged;
- if valid DECAY120, close at first aggTrade at/after T+120;
- original fee/slippage settings are applied;
- every other trade remains historical.

## DECAY120 cohort

Historical:

- N = **10**
- wins = **3**
- WR = **30.00%**
- PnL = **-$14.02**

Close-all at T+120:

- wins = **1**
- WR = **10.00%**
- PnL = **-$5.76**

Economic effect:

> **+$8.26 PnL improvement**

But:

> **-2 winners**

The system-level effect is:

| System | Wins | WR | PnL |
|---|---:|---:|---:|
| Historical | 63 | 30.14% | -$126.42 |
| Cut-all DECAY120 | 61 | 29.19% | -$118.16 |

So:

- PnL improves **+$8.26**
- WR falls **-0.95 percentage points**

Conclusion:

> velocity decay contains real loss information, but unconditional loss cutting destroys recovery winners.

---

# 3. Action B — Loss-cut only

Rule:

```
if DECAY120
AND executable T+120 PnL <= 0
    close
else
    keep historical lifecycle
```

Result:

- full PnL: **-$119.96**
- improvement: **+$6.46**
- wins: **60**
- WR: **28.71%**

Delta:

- PnL: **+$6.46**
- wins: **-3**
- WR: **-1.43 pp**

This is worse than cut-all from a win-preservation perspective.

Conclusion:

> being negative at T+120 is not sufficient reason to exit; several eventual winners are still negative at that checkpoint.

---

# 4. Action C — Profit-lock only

Rule:

```
if DECAY120
AND executable T+120 net PnL > 0
    close and bank profit
else
    continue historical lifecycle
```

This is fully causal.

It does not use future labels.

## Result

Full 209-trade system:

| System | Wins | WR | PnL |
|---|---:|---:|---:|
| Historical | 63 | 30.14% | -$126.42 |
| DECAY120 positive-profit lock | **64** | **30.62%** | **-$124.62** |

Delta:

> **+$1.80 PnL**

and:

> **+1 winner**

WR:

> **+0.48 percentage points**

The improvement came from one Validation RTF that was still profit-positive at T+120 but later closed negative.

No historical winner was harmed by this rule in the frozen sample.

However the actionable count is extremely small.

Therefore:

> **PASS as a research management candidate, not production-ready.**

---

# 5. Strong path remains valuable only from the original entry

The highest-quality V2 path was:

```
EARLY60
-> still alive
-> STRONG120
```

Historical result:

- N = **24**
- wins = **20**
- WR = **83.33%**
- PnL = **+$106.05**

Split:

| Split | N | Wins | WR | PnL |
|---|---:|---:|---:|---:|
| TRAIN | 12 | 9 | 75.00% | +$83.30 |
| VALIDATION | 8 | 8 | 100.00% | +$19.20 |
| RESERVE | 4 | 3 | 75.00% | +$3.55 |

This confirms the state is genuinely associated with good original entries.

But that does **not** imply waiting until T+120 is a good entry strategy.

---

# 6. Delayed-entry replay rejects chasing the confirmation

V3 replayed fresh entries using:

- the actual checkpoint market price;
- the same initial notional;
- fresh entry fee/slippage;
- historical close time;
- fresh exit fee/slippage.

## Enter only at T+60 after EARLY60 confirmation

- N = **40**
- wins = **16**
- WR = **40.00%**
- PnL = **+$2.79**

Split WR:

- TRAIN: **45.45%**
- VALIDATION: **30.77%**
- RESERVE: **40.00%**

## Enter only at T+120 after STRONG120 confirmation

- N = **31**
- wins = **11**
- WR = **35.48%**
- PnL = **+$29.76**

Split WR:

- TRAIN: **50.00%**
- VALIDATION: **20.00%**
- RESERVE: **20.00%**

This is decisive.

The 75–80% historical classification quality of STRONG120 is **not** an entry edge at T+120.

By the time confirmation appears:

> much of the favorable move has already happened.

Therefore:

> **DO NOT use STRONG120 as a delayed-entry signal.**

It is a **management / continuation-confidence signal for positions already entered earlier.**

---

# 7. Why velocity still matters

The executable V3 result resolves the apparent contradiction.

Velocity is useful for:

- identifying positions whose original entry is developing correctly;
- distinguishing continuation from decay;
- deciding when a currently profitable decay trade should bank profit;
- deciding when not to chase a late move.

Velocity is not sufficient for:

- turning the entire 209 OPEN_LANE universe into a 60% WR system;
- blindly cutting every decaying position at T+120;
- entering late at T+60/T+120.

So the correct role is:

> **post-entry state management**

not:

> **late entry replacement.**

---

# 8. Revised router

Research state machine:

```
ORIGINAL ENTRY
      |
      v
T+60
      |
      +-- no EARLY60
      |      -> historical / other management
      |
      +-- EARLY60
              |
              v
           T+120
              |
              +-- STRONG120
              |      -> KEEP / RUNNER confidence
              |
              +-- DECAY120
                     |
                     +-- net PnL > 0
                     |      -> BANK PROFIT candidate
                     |
                     +-- net PnL <= 0
                            -> DO NOT auto-cut
                               further loss-protection research needed
```

Important:

> a negative T+120 decay state is not enough to justify exiting.

Some eventual winners recover from that state.

---

# 9. Main numerical result

The most useful current comparison is:

| Policy | Full WR | Full PnL | Delta PnL | Delta Wins |
|---|---:|---:|---:|---:|
| Historical | 30.14% | -$126.42 | — | — |
| Cut all DECAY120 | 29.19% | -$118.16 | **+$8.26** | -2 |
| Cut negative DECAY120 only | 28.71% | -$119.96 | **+$6.46** | -3 |
| **Bank positive DECAY120 only** | **30.62%** | **-$124.62** | **+$1.80** | **+1** |

The profit-lock-only rule is the only tested V3 action that improves both:

- realized PnL;
- realized winner count.

But sample size is too small for production promotion.

---

# Final verdict

## Velocity thesis

**CONFIRMED as a post-entry state signal.**

## STRONG120

**KEEP as continuation-confidence research state.**

Do not use it as a delayed-entry signal.

## DECAY120

**Useful, but not enough for unconditional loss cutting.**

## Positive-profit DECAY120 lock

**Best safe action candidate in V3.**

Small positive effect:

- +$1.80
- +1 winner
- no winner harm observed

but extremely small sample.

## Production

**HOLD.**

No runtime order authority is changed.

---

# Next research direction

The next useful problem is now narrower:

> **within negative DECAY120, distinguish recovery winner vs true loser before cutting.**

That means analyzing the 10 valid DECAY120 trades using:

- T+60 -> T+120 velocity slope;
- current return at T+120;
- recovery velocity from local MAE;
- MFE timing;
- supply ETA change;
- flow decay;
- acceleration sign;
- route/family state.

The objective is not another generic entry filter.

It is:

> identify which negative decay trades are recoverable and which are toxic.

Only then should a negative-loss cut be considered for production.