# PP V4-3A — Low-Retention Failure Anatomy

Status: **COMPLETE — RESEARCH ONLY**

## Population

Positive clean-MFE trades available: **170**.

Trades finishing below 75% of true clean MFE:
- all positive-MFE low-retention: **164**
- protection actually fired: **56** ← primary Stage3A failure set
- NO_ACTION: **108**

Current protector fired on 62 trades total:
- >=75% true-MFE retention: **6**
- <75% true-MFE retention: **56**

## Primary failure anatomy

| Primary cause | N | Share |
|---|---:|---:|
| PARTIAL_REDUCE_DRAG | **37** | **66.07%** |
| RUNNER_TRIGGER_DELAY | **9** | **16.07%** |
| OBSERVATION_MISS | **8** | **14.29%** |
| EXECUTION_ACCOUNTING_DRAG | **2** | **3.57%** |

The dominant problem is **not 5s peak observation**.

Of 56 active failures:
- **48 / 56 = 85.71%** had an archived 5s observed peak at or above 80% of true clean MFE.
- only **8 / 56 = 14.29%** never exposed the 80% target to the protector.

Therefore most active failures occur **after enough upside was already observable**.

## Cause 1 — Partial-reduce drag

N = **37**.

Typical profile:
- median clean MFE: **0.793%**
- median observed capture of true MFE: **97.08%**
- median final retention vs true MFE: **0.96%**
- median shortfall to 80%-of-true target: **0.627 percentage points**

All 37 used **REDUCE25 only**.

Interpretation:
the system frequently saw nearly the full favorable excursion, but protected only 25% and allowed the remaining 75% to continue under the old lifecycle. Much of the already-seen profit was then given back.

This dominates smaller and medium winners:
- MFE 0.5–1.0%: **28 / 31** failures are partial-reduce drag.
- MFE 1.0–1.5%: **7 / 9** are partial-reduce drag.

Examples:
- RIVER: true MFE 1.34%, observed 1.34%, protected -0.38%.
- GRASS: true 0.98%, observed 0.94%, protected -0.59%.
- ZRO: true 0.79%, observed 0.70%, protected -0.48%.
- MAVIA: true 1.50%, observed 1.50%, protected +0.22%.

## Cause 2 — Runner-trigger delay

N = **9**.

Typical profile:
- median clean MFE: **2.25%**
- median observed capture: **93.29%**
- median final retention: **41.93%**
- median shortfall to 80% target: **1.235 pp**

The observer usually captured the runner well, but the 90%-of-running-peak condition plus 2-sample confirmation allowed substantial giveback before CLOSE.

Examples:
- US: true MFE 7.66%, observed 7.45%, runner-close trigger 5.42%, final protected 2.22%.
- AVAAI: true 4.28%, observed 4.11%, trigger 1.96%, final 1.79%.
- FLOW: true 3.14%, observed 2.93%, trigger 1.31%, final 1.14%.
- COMP: true 3.11%, observed 2.79%, trigger 1.43%, final 1.25%.

For true MFE >3%, **4 / 5** failures are runner-trigger delay.

## Cause 3 — Observation miss

N = **8**.

Typical profile:
- median clean MFE: **1.21%**
- median observed capture: **68.63%**
- median final retention: **10.73%**

Here 5s observation itself never captured 80% of true MFE.

Examples:
- ON: true 3.07%, observed 2.40%.
- AT: true 1.93%, observed 1.11%.
- CTSI: true 1.02%, observed 0.70%.
- AR: true 0.76%, observed 0.50%.

Three trades additionally missed runner qualification because true MFE exceeded 1.5% but observed peak never reached +1.5%.

## Cause 4 — Execution/accounting drag

N = **2**.

These trades had:
- observed peak >=80% of true MFE;
- runner action trigger >=80% of true MFE;
- but final net result still <75% after fees/slippage/prior reductions.

Cases:
- MEGA
- AIOT

This is a small minority.

## Secondary NO_ACTION population

There are **108** positive-MFE trades below 75% retention where the current protector did not fire at all.

Important result:

> **108 / 108 had archived observed peak < +0.50%.**

So these are not confirmation failures. They simply never entered the current +0.50% protection arm.

They belong to a separate small-profit coverage problem, not the primary active-protector failure set.

## MFE-band anatomy

| True clean MFE | Failures | Dominant cause |
|---|---:|---|
| 0.5–1.0% | 31 | PARTIAL_REDUCE_DRAG 28 |
| 1.0–1.5% | 9 | PARTIAL_REDUCE_DRAG 7 |
| 1.5–2.0% | 8 | mixed |
| 2.0–3.0% | 3 | RUNNER_TRIGGER_DELAY 2 |
| >3.0% | 5 | RUNNER_TRIGGER_DELAY 4 |

This shows two distinct engineering problems:

1. **small/medium positive trades:** too little of the observed profit is locked;
2. **large runners:** close confirmation happens too late after a well-observed peak.

## Stage3A decision

Proceed to **V4-3B — 80% Feasibility Ceiling**.

Stage3B should not immediately tune thresholds. It should first answer whether, after the true peak occurs, a causal executable opportunity at >=80% of true MFE actually remains available long enough to capture.

Priority order for Stage3B:
1. 9 RUNNER_TRIGGER_DELAY trades;
2. 37 PARTIAL_REDUCE_DRAG trades;
3. 8 OBSERVATION_MISS trades as observability-control cases;
4. 2 execution/accounting cases.

No runtime change. No paper/prospective validation. No protection authority.
