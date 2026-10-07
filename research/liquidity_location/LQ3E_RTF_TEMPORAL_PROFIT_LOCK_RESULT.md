# LQ-3E — RTF Temporal Decay / Profit-Lock Timing

Status: **PASS DIAGNOSIS / TARGET 60% NOT MET AT 1-MINUTE CADENCE**

Version: `lq3e-rtf-temporal-profit-lock-v1`

## Objective

LQ-3D reduced the OPEN_LANE universe to a 76-trade admission cohort:

- GOOD: **28**
- BAD: **10**
- RIGHT_THEN_FAILURE (RTF): **38**

Historical result:

- Wins: **28 / 76**
- WR: **36.84%**
- Net PnL: **-$45.81**

The problem after LQ-3D is therefore sharply defined:

> BAD admission is already much smaller.  
> The dominant remaining population is RTF: trades that were directionally right, reached useful MFE, then gave the move back.

LQ-3E asks:

1. When do GOOD and RTF begin to separate?
2. Can T+1 / T+2 / T+3 profit-locking reach the >60% WR target?
3. If not, can a conservative 1-minute hard-profit-floor replay do it?
4. Is the remaining issue classification or execution latency?

No production order authority is changed.

---

## 1. GOOD vs RTF temporal separation

Entry-time GOOD-vs-RTF separation was weak in LQ-3D.

After entry, the classes begin to diverge.

Best causal temporal features:

| Feature | GOOD vs RTF AUC |
|---|---:|
| T+3 selected slope5 norm | **0.687** |
| T+2 side return | **0.675** |
| T+3 side return | **0.673** |
| T+3 VWAP extension | ~0.668 |
| T+3 taker share | ~0.646 |

Typical direction:

- GOOD maintains stronger positive side-return and slope.
- RTF starts flattening / decaying by T+2/T+3.

The separation is meaningful, but not clean enough for a hard binary classifier.

---

## 2. Discrete T+1 / T+2 / T+3 profit-lock upper bound

Before tuning a rule, LQ-3E calculated the best possible causal outcome if an oracle could choose the most favorable checkpoint among T+1 / T+2 / T+3.

RTF with net-positive close available:

| Checkpoint | RTF positive |
|---|---:|
| T+1 | **7 / 38** |
| T+2 | **11 / 38** |
| T+3 | **13 / 38** |
| Positive at any T+1/T+2/T+3 | **16 / 38** |

By split, the 16 convertible RTF are:

- TRAIN: 7
- VALIDATION: 4
- RESERVE: 5

Even with perfect checkpoint choice and zero winner harm:

```
28 existing winners
+16 rescued RTF
=44 winners
```

Final theoretical WR:

> **44 / 76 = 57.89%**

The target requires at least:

> **46 / 76 = 60.53%**

Therefore:

> **T+1/T+2/T+3 discrete decision timing is mathematically insufficient for the 60% target.**

This is an important negative result.

The lost edge happens either:

- between minute checkpoints;
- before T+1;
- or later than T+3 but before historical failure.

---

# 3. Conservative historical 1-minute replay

Because the minute checkpoints were insufficient, LQ-3E replayed Binance USD-M **1m historical klines** for six hours after entry.

The replay is intentionally conservative.

## Causality rules

A profit-lock policy may only arm after a completed 1m bar proves the MFE threshold.

The stop is only active starting on the **next** 1m bar.

If the next bar opens through the floor:

> fill at the worse bar open.

Otherwise:

> fill at the floor when the bar low crosses it.

This avoids ambiguous assumptions about whether the high or low happened first inside the same candle.

Trading economics:

- Initial notional: $500
- Entry fee: 0.075%
- Exit fee: 0.075%
- Exit slippage: 2 bps
- Existing frozen entry fill is used.

To reduce use of post-close market data, the path is guarded using the frozen historical MFE:

> once a later bar exceeds historical trade MFE by more than 0.05 percentage points after the frozen peak region, the remaining path is excluded.

This is still less precise than raw aggTrades, so the replay is treated as conservative research, not execution authority.

---

# 4. Arm 0.50% + fixed +0.18% profit floor

Policy:

```
once observed MFE >= 0.50%
    arm profit protection

if market later reaches gross +0.18%
    close
```

Result:

- Wins: **40 / 76**
- WR: **52.63%**
- Approx. PnL: **-$50.70**

This substantially improves WR from 36.84%, but fixed-floor behavior damages economics by capping genuine winners.

Therefore:

> fixed +0.18% alone is not the answer.

---

# 5. Runner-preservation hybrid

Best tested economic policy:

```
MFE < 1.0%:
    after MFE >= 0.50%
    hard floor = +0.18%

MFE >= 1.0%:
    floor = max(+0.18%, 60% of observed peak)
```

Named:

> **ARM 0.50 / LOCK 0.18 / RUNNER PRESERVE 60**

## Result

| Split | N | Wins | WR | Approx. PnL |
|---|---:|---:|---:|---:|
| TRAIN | 44 | 22 | **50.00%** | -$4.14 |
| VALIDATION | 19 | 11 | **57.89%** | **+$1.66** |
| RESERVE | 13 | 7 | **53.85%** | -$4.68 |
| ALL | **76** | **40** | **52.63%** | **-$7.16** |

Historical comparison:

| System | WR | PnL |
|---|---:|---:|
| Historical | **36.84%** | **-$45.81** |
| 0.50 / 0.18 / RP60 | **52.63%** | **-$7.16** |

This is a major economic improvement:

- WR: **+15.79 percentage points**
- PnL improvement: roughly **+$38.65**
- system moves close to breakeven

But:

> **52.63% is still below the user's >60% target.**

---

# 6. Earlier arm test

To determine whether 0.50% arming itself is too late, LQ-3E lowered the arming threshold.

Best broad earlier-arm result:

> **arm 0.40% + fixed floor 0.18%**

Result:

- Wins: **42 / 76**
- WR: **55.26%**
- Approx. PnL: **-$53.24**
- RTF rescued: **17 / 38 = 44.74%**

Split WR:

- TRAIN: **24 / 44 = 54.55%**
- VALIDATION: **10 / 19 = 52.63%**
- RESERVE: **8 / 13 = 61.54%**

This is the highest WR among the tested conservative 1m policies.

However, it is economically worse than the 0.50 / 0.18 / RP60 hybrid.

Why?

Because earlier arming exposes genuine winners to the same 1-minute latency problem.

Some GOOD trades:

1. move above +0.40%;
2. arm the protection;
3. give back rapidly inside the same minute;
4. next candle opens below the intended +0.18% floor;
5. conservative replay fills below the floor.

Thus:

> lowering the arm threshold improves rescue coverage but increases latency-related winner harm.

---

# 7. Key diagnosis: the remaining problem is intra-minute

The 1-minute results explain why simply retuning PP thresholds has plateaued.

At 1m cadence:

- arming happens after the completed candle;
- a fast pump-and-fade can move from +0.5% to below breakeven before protection becomes executable;
- lowering the arm threshold does not fully fix this because the delay remains one candle.

This means the remaining gap is not primarily:

> "find another static entry filter"

or:

> "find another 1m threshold."

It is:

> **arm and enforce the profit floor fast enough after MFE is achieved.**

---

# 8. Why the theoretical ceiling is much higher

By label construction:

> every RTF trade reached MFE >=0.50% and ultimately realized non-positive.

There are:

- 28 historical GOOD winners
- 38 RTF trades
- 10 BAD trades

If a hard positive profit floor were armed **immediately** when MFE crosses 0.50%, and execution could enforce +0.18% without material gaps, the continuity upper bound is:

```
28 GOOD
+38 RTF converted
=66 winners
```

Theoretical WR:

> **66 / 76 = 86.84%**

This is **not** an executable backtest result.

It is only a mathematical upper bound showing that:

> the opportunity exists in the price path, but current timing is failing to capture it.

---

# 9. Why exact 100ms replay was not completed

LQ-3E attempted to move from 1m bars to compressed aggregate trades.

The live Binance compressed aggTrades endpoint rejected the historical Sep 29–30 queries with:

> code `-4166` — search window restricted to recent 2 days.

The correct source for these dates is Binance Vision historical daily aggTrades.

During this stage, the authorized `core-prod` Desktop Commander relay went offline, so Binance Vision could not be pulled into the VPS for the final 100ms replay.

Therefore the frozen LQ-3E result is deliberately limited to:

- full temporal checkpoint analysis;
- full conservative 1m replay;
- no fake/extrapolated 100ms result.

---

# LQ-3E verdict

## PASS — diagnosis

The RTF problem is now localized.

### Entry layer

GOOD and RTF overlap too heavily at entry to solve this with static admission alone.

### Minute checkpoint layer

Even an oracle selecting T+1/T+2/T+3 cannot reach 60%.

Maximum:

> **57.89%**

### Conservative 1m PP layer

Best WR:

> **55.26%**

Best economics:

> **52.63% WR / -$7.16**

compared with:

> **36.84% WR / -$45.81 historical**

### Remaining bottleneck

> **sub-minute MFE arm + immediate profit-floor enforcement**

---

# Production decision

**HOLD.**

Do not deploy the LQ-3E rules to order authority yet.

The best 1m rules are materially better than historical lifecycle, but still fail the target-60 gate and remain sensitive to one-minute gap-through behavior.

---

# Next required validation

The next experiment should be extremely narrow:

> **sub-minute exact profit-floor replay**

Contract:

1. use historical Binance Vision aggTrades;
2. arm immediately when MFE crosses 0.50%;
3. set executable floor at +0.18%;
4. for MFE >=1%, test runner preservation 50/60/70%;
5. replay exact timestamp ordering;
6. measure:
   - RTF rescue;
   - GOOD preservation;
   - Correct Runner PnL retention;
   - TRAIN / VALIDATION / RESERVE WR;
   - final PnL;
7. production gate:
   - WR >=60% in every split or strong pooled evidence with no Reserve collapse;
   - no material runner destruction.

The key question is no longer whether profit protection matters.

It does.

The question is whether:

> **the floor can be armed and enforced fast enough.**
