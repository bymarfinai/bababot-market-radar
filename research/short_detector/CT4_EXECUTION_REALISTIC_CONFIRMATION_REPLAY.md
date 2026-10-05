# SHORT-CT4 — Exact Execution-Realistic Confirmation Replay

Status: **PASS execution replay / +0.075% remains stability primary / +0.10% is raw-economic challenger / profitability still FAIL**

## Objective

CT-4 tests the confirmation candidates carried from CT-1 to CT-3 with actual executable entry timing and the frozen SHORT Profit Protector.

Candidates:

1. **0.0338983050847%** — baseline
2. **0.05%** — conservative
3. **0.075%** — stability primary
4. **0.10%** — aggressive economic challenger

Frozen:
- S10D architecture except Lane-1 temporal confirmation threshold
- fast T0 lane
- Lane-0 recovery
- alternate T+3 rescue
- router
- execution contract
- V4.3 SHORT-LS4
- BE0.10 only when V4.3 remains NO_ACTION
- fee, slippage and notional metadata

No Profit Protector tuning is performed.

---

# Replay method

For positions whose entry lane is unchanged, CT-4 reuses the authoritative S10F/S10J-5 baseline execution replay.

For positions whose stricter threshold changes the entry lane:

> T+1 → T+2  
> T+1 → T+3  
> T+2 → T+3

CT-4 reconstructs the new executable entry:

> open of the first complete Binance USD-M 1-minute bar strictly after the new temporal target

and replays the exact Binance aggTrade path from the new entry to historical close.

Market-data integrity for shifted research trades:
- shifted timing keys: 56
- required kline symbol-days: 48
- required aggTrade symbol-days: 41
- missing klines: **0**
- missing aggTrade: **0**

Fresh replay uses the already complete S10J-5 market archive.

Replay-engine benchmark:
- **29 / 29 valid comparable research trades reproduce baseline PnL exactly**
- max absolute difference: **0.0**

One FLOW row was excluded from the benchmark because the new T+3 target occurs after historical close, so no agg archive was required for that position by CT-4. The earlier benchmark helper incorrectly treated the unavailable baseline path as a replay mismatch.

---

# Headline execution-realistic result

## Research

| Threshold | Selected | Executable | Exec strong | Strong retention | Protected WR | Protected PnL | Delta vs baseline |
|---|---:|---:|---:|---:|---:|---:|---:|
| **0.0339%** | 364 | 320 | 80 | 100% | 32.50% | **-$180.54** | — |
| 0.05% | 350 | 307 | 79 | 98.75% | 32.57% | **-$162.75** | **+$17.80** |
| **0.075%** | **333** | **291** | **78** | **97.50%** | **33.68%** | **-$135.33** | **+$45.21** |
| 0.10% | 309 | 268 | 74 | 92.50% | 34.70% | **-$125.19** | **+$55.35** |

## Fresh S10H development

| Threshold | Selected | Executable | Exec strong | Strong retention | Protected WR | Protected PnL | Delta vs baseline |
|---|---:|---:|---:|---:|---:|---:|---:|
| **0.0339%** | 807 | 688 | 174 | 100% | 33.14% | **-$299.81** | — |
| 0.05% | 787 | 671 | 173 | 99.43% | 32.94% | **-$286.47** | **+$13.34** |
| **0.075%** | **754** | **640** | **168** | **96.55%** | **33.28%** | **-$245.06** | **+$54.76** |
| 0.10% | 718 | 605 | 163 | 93.68% | 33.72% | **-$212.35** | **+$87.46** |

All stricter confirmation candidates improve aggregate protected PnL versus 0.0339%.

However:

> **all threshold-only candidates remain negative.**

Confirmation strengthening is therefore useful, but is not sufficient by itself to solve SHORT profitability.

---

# +0.075% chronological execution result

CT-3 flagged +0.075% as the most stable threshold.

CT-4 confirms that exact execution PnL improves in **all 6 chronological blocks**.

## Research Discovery

Baseline:
> -$143.92

0.075%:
> **-$126.70**

Improvement:
> **+$17.22**

## Research Validation

Baseline:
> +$1.11

0.075%:
> **+$10.89**

Improvement:
> **+$9.78**

## Research Reserve

Baseline:
> -$37.73

0.075%:
> **-$19.52**

Improvement:
> **+$18.21**

## Fresh Oct 1

Baseline:
> -$215.42

0.075%:
> **-$182.71**

Improvement:
> **+$32.71**

## Fresh Oct 2

Baseline:
> +$25.30

0.075%:
> **+$40.21**

Improvement:
> **+$14.91**

## Fresh Oct 3

Baseline:
> -$109.69

0.075%:
> **-$102.56**

Improvement:
> **+$7.13**

This resolves the main CT-3 warning:

> although Fresh Oct 3 nominal precision fell slightly, execution-realistic protected PnL still improves.

Thus +0.075% passes both structural stability and execution-economics direction.

---

# +0.10% economic result

+0.10% is the raw PnL leader among tested thresholds.

Research:
> **-$125.19**, improvement **+$55.35**

Fresh:
> **-$212.35**, improvement **+$87.46**

It also improves PnL in all six chronological blocks.

However CT-3 showed:

- Research Reserve baseline-selected strong retention: **83.33%**
- Fresh Oct 3 strong retention: **86.11%**
- high-value research winners begin to be removed
- total removed strong baseline value rises sharply

Execution-level strong retention is:

- Research: **92.50%**
- Fresh: **93.68%**

Therefore +0.10% is now classified as:

> **economic leader / stability challenger**

not the default primary.

The decision between 0.075% and 0.10% belongs in CT-5, where winner-value preservation and architecture simplicity are adjudicated explicitly.

---

# Where the +0.075% improvement comes from

This is the most important CT-4 finding.

## Research

### Trades fully removed

Baseline PnL of removed cohort:

> **-$41.44**

Avoiding them contributes:

> **+$41.44**

### Trades shifted to later entry

Old-entry baseline PnL:

> -$26.83

New exact delayed-entry PnL:

> -$23.06

Contribution:

> **+$3.77**

Total:

> **+$45.21**

Thus research improvement comes overwhelmingly from rejecting weak setups.

## Fresh

### Trades fully removed

Baseline PnL:

> **-$66.45**

Avoiding them contributes:

> **+$66.45**

### Trades shifted later

Old-entry baseline PnL:

> **-$24.22**

Exact later-entry PnL:

> **-$35.91**

Contribution:

> **-$11.69**

Total:

> +$66.45 - $11.69 = **+$54.76**

Therefore, in fresh data:

> **the later entry itself makes the shifted cohort worse.**

The value of a stronger confirmation threshold is primarily:

> **rejecting weak setups**

rather than:

> waiting longer and obtaining a superior entry.

This materially changes the interpretation of the confirmation repair.

---

# +0.10% decomposition

## Research

Removed-cohort contribution:
> **+$39.36**

Shifted-entry contribution:
> **+$16.00**

Total:
> **+$55.35**

## Fresh

Removed-cohort contribution:
> **+$109.11**

Shifted-entry contribution:
> **-$21.65**

Total:
> **+$87.46**

The same pattern is even stronger at 0.10%:

> fresh gains are produced by vetoing weak setups, while later entry on surviving marginal trades is economically harmful.

---

# Lane economics

## Baseline fresh

- T0: **-$75.99**
- T+1: **-$128.57**
- T+2: **-$70.88**
- T+3: **-$24.37**
- total: **-$299.81**

## +0.075% fresh

- T0: **-$75.99**
- T+1: **-$65.75**
- T+2: **-$59.22**
- T+3: **-$44.10**
- total: **-$245.06**

Changes:
- T0: unchanged
- T+1: **+$62.82**
- T+2: **+$11.66**
- T+3: **-$19.73**

This exposes a new architecture issue:

> stronger confirmation cleans T+1 substantially, but some marginal setups are pushed into T+3 where economics deteriorate.

The alternate / late T+3 rescue path therefore requires explicit review in CT-5.

## +0.10% fresh

- T0: -$75.99
- T+1: **-$38.69**
- T+2: **-$50.22**
- T+3: **-$47.45**

Again:

> T+1 improves dramatically while T+3 gets worse.

---

# Strong vs non-target economics

## Baseline fresh

Strong:
> 174 executable / **+$465.29**

Non-target:
> 514 executable / **-$765.10**

## +0.075%

Strong:
> 168 executable / **+$444.39**

Strong-value change:
> **-$20.90**

Non-target:
> 472 executable / **-$689.44**

Non-target improvement:
> **+$75.66**

Net:
> **+$54.76**

## +0.10%

Strong:
> 163 executable / **+$424.68**

Strong-value change:
> **-$40.61**

Non-target:
> 442 executable / **-$637.03**

Non-target improvement:
> **+$128.07**

Net:
> **+$87.46**

This quantifies the exact trade-off:

- 0.075 sacrifices less winner value;
- 0.10 buys more loss removal by sacrificing roughly twice as much strong-winner PnL.

---

# Comparison with current S10J suppressor stack

Current accepted S10J-6B development stack, built on the original 0.0339% architecture:

> **fresh protected PnL = -$182.01**

Threshold-only results:

- 0.075%: **-$245.06**
- 0.10%: **-$212.35**

Therefore:

> strengthening confirmation alone does **not** yet outperform the normalized suppressor stack.

However these systems cannot simply be added mechanically.

Changing confirmation threshold changes:
- lane assignment,
- rolling normalized populations,
- T+1/T+2/T+3 candidate composition.

The S10J suppressors must be re-evaluated or rebuilt after a threshold is frozen.

---

# CT-4 verdict

> **CT-4 = PASS for confirmation-strengthening economics.**

The original:

> **+0.0339%**

is confirmed as too permissive.

## Stability primary

> **+0.075%**

Why:
- +$45.21 research improvement
- +$54.76 fresh improvement
- PnL improves in **6/6 chronological blocks**
- research executable strong retention **97.50%**
- fresh executable strong retention **96.55%**
- avoids the sharper block-level winner destruction seen at 0.10%

## Raw economic leader

> **+0.10%**

Why:
- +$55.35 research
- +$87.46 fresh
- best aggregate PnL among tested thresholds

But:
- failed CT-3 block-level winner-retention stability
- larger strong-value sacrifice
- remains a challenger rather than primary

## Profitability

Still:

> **FAIL**

Best threshold-only fresh result:

> **-$212.35**

Primary stability threshold:

> **-$245.06**

No runtime promotion is authorized.

---

# Critical architecture finding for CT-5

The next decision is no longer simply:

> “which threshold gives the highest PnL?”

CT-4 shows:

> **the confirmation floor works mainly as a veto.**

Later rescue / delayed entry often gives back part of the gain, especially in fresh data.

CT-5 should therefore compare at minimum:

1. **0.075% with current later-rescue behavior**
2. **0.075% with weak temporal candidates rejected instead of pushed later**
3. 0.10% economic challenger
4. whether normalized S10J suppressors are still needed after the stronger confirmation floor

The objective should be:

> preserve the stable winner-retention profile of 0.075% while capturing more of the economic benefit currently achieved by 0.10%, without creating another S10G-style regime-specific filter.

No production/runtime change is authorized by CT-4.
