# WD-3 VPS Frozen Results — 2026-10-01

Source of truth: VPS `core-prod` PostgreSQL.  
Authority: research only.  
Production rule changes: none.

## Executive result

WD-3 resolves the main A-vs-B question from WD-2:

> **Do not delay every entry. Enter normally and use a short dynamic wrong-direction discriminator.**

Pure waiting worsens economics:

| Pure delay | Matched trades | Actual net | Delayed-entry net | Delta |
|---|---:|---:|---:|---:|
| +1m | 1,190 | -$1,399.00 | -$1,460.40 | **-$61.40** |
| +3m | 950 | -$898.61 | -$1,217.43 | **-$318.81** |
| +5m | 781 | -$583.03 | -$1,051.26 | **-$468.23** |

The apparent benefit of the best delay/filter policy comes from cancelling selected bad trades, not from waiting itself.

## Best raw single-horizon dynamic exit

`5m + adverse_families_ge_2`

- full-cohort delta: **+$95.25**
- wrong capture among matched TRUE_WRONG_DIRECTION: **43.1%**
- recovered harm: **18.6%**
- runner harm: **15.0%**

This improves PnL but is too aggressive against recovered trades and acts late.

## Best raw sequential policy

`1m ret3neg+flowOpp -> 3m ret3neg+flowOpp`

- full-cohort delta: **+$103.48**
- matched cohort: 1,190
- flagged: 307
- wrong capture: **33.1%**
- recovered harm: **15.8%**
- runner harm: **18.5%**
- chronological observable-thirds deltas:
  - **+$65.41**
  - **+$19.97**
  - **+$18.10**

It is stable in aggregate but still harms too many recovered winners.

## WD-3 balanced candidate

The preferred WD-3 handoff candidate is:

### Step 1 — around +1 minute

Close if:

`side_ret_3m < 0 AND flow_opposite = true`

### Step 2 — around +3 minutes, only if still open

Close if:

`side_ret_3m < 0 AND opposite_micro_structure = true`

No production authority is assigned yet.

### Economics

- full-cohort delta: **+$100.28**
- actual full-cohort net: **-$2,338.65**
- counterfactual net: **-$2,238.37**
- matched cohort: **1,190**
- matched actual net: **-$1,399.00**
- matched policy net: **-$1,298.72**
- flagged trades: **164**
- wrong capture among matched TRUE_WRONG_DIRECTION: **17.4%**
- recovered harm: **5.8%**
- runner harm: **18.5%**

The runner percentage is based on a small high-resolution runner denominator; only **5 CORRECT_RUNNER trades** are flagged and the total runner PnL impact is **-$9.01**.

### PnL attribution

| WD-1 class | Delta |
|---|---:|
| TRUE_WRONG_DIRECTION | **+$81.08** |
| STALL_NO_EDGE | **+$91.97** |
| RECOVERED_DRAWDOWN | **-$47.22** |
| RIGHT_THEN_FAILURE | **-$16.55** |
| CORRECT_RUNNER | **-$9.01** |
| **Total** | **+$100.28** |

Among the 164 flagged trades:

- TRUE_WRONG_DIRECTION: 87
- STALL_NO_EDGE: 28
- RIGHT_THEN_FAILURE: 29
- RECOVERED_DRAWDOWN: 15
- CORRECT_RUNNER: 5

So **115/164 = 70.1%** of flags are strict wrong-direction or stall/no-edge outcomes.

## Chronological observable-thirds robustness

Balanced-candidate delta:

| Slice | Trades | Delta | Delta/trade |
|---|---:|---:|---:|
| 1 | 396 | **+$55.78** | +$0.141 |
| 2 | 397 | **+$20.41** | +$0.051 |
| 3 | 397 | **+$24.09** | +$0.061 |

All three observable time slices remain positive.

Recovered-harm rates:

- slice 1: 7.5%
- slice 2: 4.5%
- slice 3: 5.2%

## Segment robustness

Balanced candidate remains positive in every major side/stage segment tested:

| Segment | Delta |
|---|---:|
| LONG | **+$86.24** |
| SHORT | **+$14.04** |
| IGNITION | **+$16.85** |
| EXPANSION | **+$83.44** |
| LONG IGNITION | **+$6.59** |
| LONG EXPANSION | **+$79.65** |
| SHORT IGNITION | **+$10.25** |
| SHORT EXPANSION | **+$3.79** |

Most economic benefit is concentrated in LONG / EXPANSION, but no major segment is negative in this replay.

## Bootstrap diagnostic

A 5,000-resample non-parametric bootstrap of per-trade balanced-policy deltas produced:

- point delta: **+$100.28**
- 95% percentile interval: **+$41.55 to +$164.21**
- positive resample share: **99.92%**

This is an in-sample stability diagnostic, **not independent out-of-sample validation**.

## Decision

WD-3 supports **dynamic early wrong-direction protection**, not a blanket delayed-entry rule.

The balanced candidate is preferred over the raw-PnL winner because it gives up only about **$3.20** of historical delta while reducing recovered-drawdown harm from **15.8% to 5.8%**.

It should **not** be promoted directly from WD-3 because:

- the signatures were discovered and evaluated on the same frozen research cohort,
- high-resolution CORRECT_RUNNER coverage is smaller,
- no prospective shadow validation has occurred yet.

## WD-4 handoff

WD-4 should run the balanced 1m -> 3m discriminator prospectively in shadow mode:

1. production authority remains unchanged,
2. record the hypothetical trigger and counterfactual close price,
3. compare against actual lifecycle outcome,
4. require enough new independent trades before promotion,
5. separately watch recovered-drawdown false exits and runner damage.
