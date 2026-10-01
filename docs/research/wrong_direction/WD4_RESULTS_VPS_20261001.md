# WD-4 VPS Frozen Results — 2026-10-01

Source of truth: VPS `core-prod` PostgreSQL + Binance USD-M Futures historical 1m klines.  
Cohort: all 849 frozen `TRUE_WRONG_DIRECTION` trades.  
Authority: research only.  
Production rule changes: none.

## Executive result

WD-4 materially changes our understanding of the 849 wrong-direction trades.

Under the strict primary definition:

> **TP +0.5% net before SL -0.5%, within 30 minutes, after fee/slippage**

the 849 trades map to:

| Strict resolution target | Trades | Share |
|---|---:|---:|
| **Opposite side from entry = WIN** | **435** | **51.24%** |
| **Flip at +1m = WIN** | **14** | **1.65%** |
| **Flip at +3m = WIN** | **14** | **1.65%** |
| **NO TRADE target** | **386** | **45.47%** |
| **Total** | **849** | **100%** |

Therefore:

> **463 / 849 = 54.53% are strict WIN-capable under the tested resolution paths.**

The remaining **386 / 849 = 45.47%** should be treated as a **NO-TRADE target** under the strict WD-4 objective unless a later stage finds a better causal resolution.

## Main structural finding

The dominant failure is **direction selection**, not late exit.

Of the 463 strict WIN-capable trades:

- **435 / 463 = 94.0%** are resolved simply by choosing the opposite side from entry.
- only **28 / 463 = 6.0%** require a later +1m/+3m flip.

This strongly suggests a large portion of the wrong-direction problem originates before or at the Stage 4/6/11C directional decision.

## Bounded-risk robustness

The result remains similar under a wider stop:

### TP +0.5% before SL -1.0%

| Resolution | Trades |
|---|---:|
| Opposite from entry | 454 |
| Flip +1m only | 12 |
| Flip +3m only | 15 |
| NO TRADE target | 368 |

Total WIN-capable:

**481 / 849 = 56.65%**

So widening the allowed adverse move from -0.5% to -1.0% only increases the resolved set by 18 trades.

This confirms most of the primary 463 strong-win cases do **not** rely on a deep adverse excursion before recovering.

### Robust TP +1.0% before SL -1.0%

- opposite from entry: 193
- flip +1m: 5
- flip +3m: 9
- total WIN-capable: **207 / 849 = 24.38%**

These are the strongest wrong-direction cases where the opposite/flip resolution produces a full +1% net move before -1%.

## Weak opportunity layer

Within 30 minutes:

- 827 / 849 = **97.41%** become net positive under at least one of the tested paths.
- only 22 / 849 = **2.59%** never become net positive under opposite-entry, flip+1m, or flip+3m.

However, this weak-positive figure is **not** used as the primary saved-trade target because many cases only produce small transient profit.

The primary target remains the bounded-risk +0.5 / -0.5 result.

## Horizon sensitivity

Strict target union: TP +0.5% before SL -0.5%.

| Horizon | Strict WIN-capable | Share |
|---|---:|---:|
| 15m | 301 | 35.45% |
| **30m** | **463** | **54.53%** |
| 60m | 543 | 63.96% |

Extended +0.5 / -1.0:

- 15m: 308 / 849 = 36.28%
- 30m: 481 / 849 = 56.65%
- 60m: 586 / 849 = 69.02%

Robust +1.0 / -1.0:

- 15m: 89 / 849 = 10.48%
- 30m: 207 / 849 = 24.38%
- 60m: 337 / 849 = 39.69%

WD-4 keeps 30 minutes as the primary horizon so the target is not dependent on very long recovery time.

## Opposite-from-entry timing

For the 460 trades that reached an unbounded strong +0.5% net target by reversing from entry:

- median time to +0.5%: **11.48 minutes**
- 25th percentile: **6.41 minutes**
- 75th percentile: **20.35 minutes**
- 90th percentile: **25.62 minutes**

The direction-selection error therefore often develops into a meaningful opposite move within the same short intraday window.

## Original side

Under strict +0.5 / -0.5 mapping:

### Original LONG

- N = 579
- WIN-capable = 303
- share = **52.33%**
- NO TRADE target = 276

### Original SHORT

- N = 270
- WIN-capable = 160
- share = **59.26%**
- NO TRADE target = 110

The resolution opportunity exists on both sides.

## Movement stage

Under strict +0.5 / -0.5 mapping:

### IGNITION

- N = 244
- WIN-capable = 128
- share = **52.46%**

### EXPANSION

- N = 605
- WIN-capable = 335
- share = **55.37%**

The issue is therefore not isolated to one movement stage.

## What WD-4 does and does not prove

WD-4 proves that the majority of strict wrong-direction losses are **economically resolvable in hindsight**:

- 54.53% have a strict bounded-risk WIN path,
- 45.47% map to NO TRADE under the strict target.

It does **not** prove the current detector can identify those groups before the future path occurs.

The correct WD-5 task is therefore not "close losses faster." It is:

> Build a causal classifier that distinguishes **OPPOSITE_FROM_ENTRY_WIN** from **NO_TRADE_TARGET**, with secondary early-flip classes, while preserving existing good/recovered trades.

If that classifier succeeds, the end-state target becomes exactly the user's objective:

> wrong-direction cases should become **WIN or NO TRADE**, not merely smaller losses.
