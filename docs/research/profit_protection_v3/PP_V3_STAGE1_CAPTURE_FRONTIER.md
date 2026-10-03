# PP-DECISION V3 — Stage 1 Capture Frontier

Status: **COMPLETE — research benchmark only, no production authority**

## Objective

Translate the economic target into a causal benchmark:

> After a trade has reached at least +0.30% MFE, determine whether a static trailing floor can retain close to 80% of the eventual peak without destroying future runners.

Stage 1 does **not** change PP-LEGACY V3 or PP-DECISION V2 production/shadow behavior.

## Frozen dataset

- start boundary: `1790848801393`
- cutoff: `1791021852690`
- closed trades: **3,234**
- true-MFE >= +0.30%: **2,210**
- trades whose fast current PnL was actually observed >= +0.30%: **1,384**
- true-MFE eligible but never observed at/above +0.30%: **826**
- actual net PnL of full frozen cohort: **-$3,606.25**

All 2,210 true-MFE eligible positions have PP-DECISION V2 fast observations.

## Critical observability finding

The protector cannot act on a peak it never sees.

Across the 2,210 true-MFE eligible trades:

- only **62.62%** were actually observed with current PnL >= +0.30%;
- median observable peak / true MFE = **78.27%**;
- weighted observable peak / true peak = **68.38%**;
- the 826 unobserved-at-arm trades had **$3,090.25** of true-MFE gross peak opportunity but actual net PnL of **-$1,843.67**.

This means the original 80%-of-true-MFE target is already close to or above the information ceiling for many trades under the current polling architecture.

## Replay definition

For the observable-arm cohort:

1. arm only when **current PnL actually observed >= +0.30%**;
2. keep a causal running peak of observed current PnL;
3. static floor = `ratio × running observable peak`;
4. trigger on the first fast observation where current PnL <= floor;
5. poll replay exits at that observation's market price;
6. use the same paper economics:
   - fee = 0.075% per side
   - slippage = 2 bps
   - full initial quantity
7. separately calculate an **ideal floor fill** at the exact floor to isolate polling/execution latency.

## Main capture frontier

| Floor ratio | Poll net, armed cohort | Delta vs actual armed | Poll WR | Ideal capture of eventual true peak | Poll capture of eventual true peak | Poll latency cost vs ideal | Future >=1% runners exited before +1% |
|---|---:|---:|---:|---:|---:|---:|---:|
| 50% | $1,302.39 | +$264.50 | 60.40% | 32.61% | 26.07% | -$587.86 | 291 |
| 60% | $1,225.87 | +$187.98 | 72.40% | 32.14% | 25.21% | -$621.58 | 365 |
| 70% | $1,298.11 | +$260.21 | 81.21% | 33.57% | 26.02% | -$678.40 | 415 |
| 75% | $1,352.86 | +$314.97 | 84.39% | 34.52% | 26.63% | -$708.28 | 435 |
| 80% | $1,411.63 | +$373.74 | 86.71% | 35.18% | 27.28% | -$709.44 | 450 |
| 85% | $1,470.58 | +$432.69 | 88.29% | 35.97% | 27.94% | -$721.34 | 464 |
| 90% | **$1,507.58** | **+$469.69** | **89.74%** | **36.38%** | **28.35%** | **-$721.15** | **490** |

Actual net PnL for the same 1,384 observable-arm trades was **+$1,037.89**.

Within the original 50–90% grid, 90% produced the highest poll-replay net, but it still captured only **28.35% of eventual true peak**.

## Diagnostic extension

The frontier was extended only as a diagnostic, not as a frozen production threshold:

| Floor ratio | Poll net | Delta vs actual armed | Poll WR | Poll capture true peak | Future >=1% runners exited before +1% |
|---|---:|---:|---:|---:|---:|
| 92.5% | **$1,540.29** | **+$502.40** | 90.10% | 28.72% | 495 |
| 95% | $1,529.11 | +$491.22 | 90.46% | 28.59% | 506 |
| 97.5% | $1,524.30 | +$486.41 | 90.82% | 28.54% | 513 |

The net frontier plateaus around 92.5–97.5%. Tightening the static floor further mostly increases premature runner exits instead of improving eventual-peak capture.

## Why an 80% static floor does not yield 80% capture

At an 80% floor:

- ideal exact-floor execution captures only **35.18%** of eventual true peak;
- actual poll execution captures only **27.28%**;
- poll/execution latency costs about **$709.44** versus ideal exact-floor execution on the armed cohort;
- median arm-to-trigger time is roughly **45 seconds**;
- **450** trades that eventually reach >=1% are exited while their observed running peak is still <1%;
- **160** trades that eventually reach >=2% are exited while their observed running peak is still <2%.

Therefore there are three independent losses:

1. **Observability loss** — true MFE may happen between polls and never become an observed current-PnL peak.
2. **Runner-preservation loss** — a static floor exits on an early retracement before the later higher peak forms.
3. **Execution-latency loss** — even after a floor breach, poll-based execution occurs materially below the intended floor.

## Chronological robustness

The static policies are not stable enough for promotion.

### 80% floor
- early third: **+$286.07** vs actual
- middle third: **+$176.57**
- late third: **-$88.90**

### 90% floor
- early third: **+$347.75**
- middle third: **+$187.63**
- late third: **-$65.69**

### 92.5% diagnostic
- early third: **+$363.79**
- middle third: **+$203.65**
- late third: **-$65.03**

The late cohort reverses the improvement, so no static ratio is robust enough to become authority.

## Stage 1 conclusion

**Stage 1 succeeds as a frontier study but static trailing protection FAILS the 80% capture objective.**

The next engineering problem is no longer “which single trailing percentage is best.”

Stage 2 must solve:

- dynamic floor strength instead of one static ratio;
- runner-preservation / retracement continuation logic;
- explicit separation between observed peak and true MFE;
- execution architecture capable of reducing the large poll-latency gap.

No production threshold is changed by Stage 1.

## Reproducibility

- script: `research/profit_protection_v3/stage1_capture_frontier.py`
- frozen result: `research/profit_protection_v3/results/stage1_capture_frontier_1791021852690.json`
- tests: `tests/test_pp_v3_stage1_capture_frontier.py`
