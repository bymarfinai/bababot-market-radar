# SHORT-S10H — Fresh Sealed Forward Validation

Status: **SEALED FRESH FAIL — production promotion rejected**

## Objective

Validate the fully frozen S10G SHORT detector on data that occurred strictly after the research dataset cutoff.

No S10G threshold, router coefficient, lane rule, veto rule, execution rule, or Profit Protector parameter was changed after opening the fresh cohort.

Frozen protector:

> **V4.3 SHORT-LS4 + BE0.10 on the V4.3 NO_ACTION lane**

## Seal boundary

Frozen research data ended at:

> **2026-10-01 03:34:59.999 UTC**  
> cutoff ms: **1790825699999**

Fresh authoritative PostgreSQL cohort:

- **1,721 SHORT paper positions**
- all opened strictly after the cutoff
- all CLOSED
- first open: 2026-10-01 03:41:52.534 UTC
- last open: 2026-10-03 22:20:35.537 UTC
- last close: 2026-10-03 23:35:15.201 UTC

These positions were actual paper positions produced by the live pipeline, not synthetic signal candidates.

## Data reconstruction integrity

Fresh features were rebuilt using the same frozen research functions used by the prior wrong-direction / SHORT research stack.

Market archives:

- 923 Binance USD-M 1m kline symbol-date files
- 909 Binance USD-M OI-metrics symbol-date files
- **0 missing**
- **0 errors**

Fresh feature reconstruction:

> **1,721 / 1,721 successful, 0 feature errors**

The frozen Stage3A primary meta-label contract was reused:

> net TP +0.5% / SL -0.5% / 30-minute horizon

Fresh labels:

- META_LOSS: **1,031**
- META_WIN: **418**
- TIMEOUT: **272**

As in the prior SHORT research, TIMEOUT is excluded from the resolved detector universe.

Resolved fresh universe:

> **1,449**

Fresh strong-WIN definition remains:

> META_WIN AND observed historical MFE >= 1.0%

Fresh strong targets:

> **261**

## Frozen S10G selection on fresh data

S10G selected:

> **516 / 1,449 resolved trades**

Strong targets selected:

> **112 / 261**

Metrics:

- nominal strong recall: **42.91%**
- selected precision: **21.71%**
- fresh baseline strong prevalence: **18.01%**
- selection lift: **1.21x**

For comparison, S10G research:

- strong recall: **79.80%**
- selected precision: **35.11%**
- baseline prevalence: 15.11%
- selection lift: **2.32x**

The principal fresh degradation is therefore a collapse in target discrimination.

### Selected lane counts

- T0: 162
- T+1: 73
- T+2: 171
- T+3: 110

## Execution-realistic replay

The same S10F/S10G execution contract was applied:

- T0: original paper executable entry
- T+1/T+2/T+3: first Binance 1m bar open strictly after the qualifying target
- no execution when the original fresh position had already closed before delayed entry
- exact Binance aggTrade path after reconstructed entry
- frozen fees/slippage metadata
- V4.3 5-second sampling
- BE0.10 only on V4.3 NO_ACTION
- actual fresh paper close time as fallback

Required aggTrade archives:

- 353 symbol-date files
- **0 missing**
- **0 errors**

Result:

> **516 selected → 432 executable → 84 no-executable**

Executable strong targets:

> **104**

## Fresh economics

| Policy | Executable | Wins | WR | PnL |
|---|---:|---:|---:|---:|
| Delayed hold | 432 | 101 | 23.38% | **-$464.03** |
| V4.3 | 432 | 146 | 33.80% | **-$448.41** |
| **V4.3 + BE0.10** | **432** | **145** | **33.56%** | **-$179.30** |

The frozen composite still provides large loss compression:

> **+$284.73 vs delayed hold**

but does not restore profitability.

For reference, the actual old paper lifecycle PnL on these same 432 selected/executable positions was:

> **-$225.06**

## Strong vs non-target economics

### Strong cohort

104 executable strong targets:

- protected-positive: **89 / 104**
- protected WR: **85.58%**
- protected PnL: **+$290.78**
- gross loss: only **-$10.41**

Thus the strong-winner opportunity itself remains highly monetizable.

### Non-target cohort

328 executable non-targets:

- protected-positive: 56 / 328
- protected WR: 17.07%
- protected PnL: **-$470.08**

Therefore:

> the sealed failure is driven by fresh false-positive selection, not by Profit Protector failure on genuine winners.

## Lane economics

Every frozen lane is negative on aggregate fresh data:

| Lane | Executable | Strong | Protected WR | Protected PnL |
|---|---:|---:|---:|---:|
| T0 | 162 | 36 | 33.95% | **-$46.04** |
| T+1 | 66 | 14 | 30.30% | **-$50.26** |
| T+2 | 127 | 37 | 33.86% | **-$59.88** |
| T+3 | 77 | 17 | 35.06% | **-$23.12** |
| **Total** | **432** | **104** | **33.56%** | **-$179.30** |

This means the fresh failure is broader than the prior research-only T+1/T+2 issue.

The previously positive T0 and T+3 lanes also fail to transport.

## Chronological stability

| Fresh day (UTC) | Executable | Strong | Protected WR | Protected PnL |
|---|---:|---:|---:|---:|
| 2026-10-01 | 182 | 43 | 35.16% | **-$114.06** |
| 2026-10-02 | 155 | 44 | 34.84% | **+$16.18** |
| 2026-10-03 | 95 | 17 | 28.42% | **-$81.42** |

Two of three fresh days are negative.

Chronological halves:

- first 216 trades: **-$140.54**
- second 216 trades: **-$38.76**

There is some improvement in the second half, but it remains negative.

## Research vs fresh sealed

| Metric | S10G research | S10H fresh sealed |
|---|---:|---:|
| Resolved universe | 655 | 1,449 |
| Selected | 225 | 516 |
| Strong targets | 99 | 261 |
| Strong selected | 79 | 112 |
| Strong recall | **79.80%** | **42.91%** |
| Selection precision | **35.11%** | **21.71%** |
| Selection lift | **2.32x** | **1.21x** |
| Executable | 199 | 432 |
| Executable strong | 75 | 104 |
| Protected WR | **47.24%** | **33.56%** |
| Protected PnL | **+$76.98** | **-$179.30** |

## Verdict

> **SHORT-S10H = SEALED FAIL.**

S10G must **not** be promoted to runtime production logic.

The fresh test demonstrates that the research frontier materially overfit / failed to generalize to the immediate forward regime.

The key failure is:

> **selection discrimination collapsed out of sample.**

The fresh strong cohort remains highly profitable once found, which means the underlying opportunity still exists. The next development task should focus on discovering why the frozen detector admits 328 fresh non-targets while capturing only 104 executable strong targets.

## Methodology rule going forward

This 1,721-position fresh cohort is now **opened** and must never be reused as a sealed validation set.

It may be used only as a failure-diagnosis / development dataset.

Any repair derived from S10H must subsequently be validated on a **new later forward window that was not used for repair**.

No runtime trading changes are authorized by S10H.
