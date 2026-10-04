# PP V4-3B — Giveback Window Anatomy

Status: **COMPLETE — RESEARCH ONLY**

Baseline under study:

> **Profit Protector V4.2 — Hybrid Protection**

No runtime or protection authority was changed.

## Population

V4.2 protection actually fired on **62 historical trades**:

- **56** finished below 75% of true clean MFE;
- **6** finished at or above 75% and are retained as controls.

The full archived 5s path produced **1,751 causal giveback-crossing events** across 95%, 90%, 85%, 80%, and 75% of the then-current running observed peak.

Future path is used only to label whether a historical crossing eventually recovered to a new high. That label is research-only and is not a runtime feature.

## Finding 1 — A fixed 80% trailing floor is not safe

Across all historical running-peak episodes:

| Giveback threshold | Events | Later recovered to new high | Recovery share |
|---|---:|---:|---:|
| 95% | 464 | 402 | **86.64%** |
| 90% | 387 | 325 | **83.98%** |
| 85% | 338 | 276 | **81.66%** |
| 80% | 298 | 236 | **79.19%** |
| 75% | 264 | 202 | **76.52%** |

Therefore simply closing the first time profit falls to 80% of the current running peak would cut many trades that later continue higher.

At the 80% level:

- **60 / 62 trades** had at least one crossing that later recovered to a new high;
- median recovered 80%-crossings per trade: **4**;
- **45 / 62** had at least 3;
- **19 / 62** had at least 5;
- maximum: **9**.

This is the strongest Stage3B evidence that the problem is not solved by a single trailing percentage.

## Finding 2 — Peak regime changes the meaning of an 80% crossing

80%-crossing recovery rate by running-peak magnitude:

| Running observed peak | 80% crossing events | Later new high | Recovery share |
|---|---:|---:|---:|
| <1% | 244 | 210 | **86.07%** |
| 1–1.5% | 24 | 15 | **62.50%** |
| 1.5–3% | 23 | 8 | **34.78%** |
| >=3% | 7 | 3 | **42.86%** |

Interpretation:

- on small peaks, an 80% giveback is usually normal noise / pullback;
- once a trade becomes a meaningful runner, an 80% crossing becomes materially more informative;
- therefore one universal giveback ratio should not govern all peak sizes.

## Finding 3 — Final reversal has a measurable time window

After the **final observed 5s peak**, median time to each floor across all 62 trades:

| Floor | Median from final observed peak | P25 | P75 |
|---|---:|---:|---:|
| 95% | **5.19s** | 5.00s | 13.81s |
| 90% | **10.13s** | 5.07s | 24.97s |
| 85% | **17.47s** | 9.92s | 40.08s |
| 80% | **24.95s** | 10.00s | 70.05s |
| 75% | **34.92s** | 15.02s | 90.02s |

The window is materially wider for larger runners.

Median time from final observed peak to 80%:

- peak <1%: **12.61s**
- peak 1–1.5%: **25.03s**
- peak 1.5–3%: **60.02s**
- peak >=3%: **62.62s**

This is important: large runners generally give the protector more time to distinguish a real reversal before the 80% floor is lost.

## Finding 4 — Time and downward velocity separate transient vs final reversal better than streak count alone

At historical 80%-crossing events:

### Transient / recovered crossings

- median age since running peak: **10.13s**
- median downward velocity: **0.0154 percentage-points/sec**
- median monotonic down-streak: **2 observations**

### Final-reversal crossings

- median age since running peak: **24.95s**
- median downward velocity: **0.0366 percentage-points/sec**
- median monotonic down-streak: **2 observations**

So final reversals were, on median:

- older relative to the last running peak;
- falling more than twice as fast.

Simple consecutive-down count did **not** separate the classes well because both groups had a median streak of 2.

Candidate Stage3C causal features are therefore:

1. running-peak regime;
2. seconds since last new running high;
3. downward PnL velocity;
4. reclaim / failure-to-reclaim behavior.

## Finding 5 — Stage3A RUNNER_TRIGGER_DELAY needs temporal refinement

There were **19 V4.2 runner CLOSE actions**.

Temporal relation to the highest later archived observed peak:

- **9** closed before a later higher peak appeared;
- **10** closed after the final observed peak.

Among runner-close failures:

- **8** were premature-before-later-higher-peak;
- **5** were after-final-peak.

Most importantly, the 9 trades Stage3A labelled `RUNNER_TRIGGER_DELAY` split into:

- **7 / 9** = V4.2 runner close occurred **before a later higher peak**;
- **2 / 9** = close occurred after the final peak.

Therefore the Stage3A label was directionally useful as a low-retention bucket, but Stage3B shows the dominant temporal mechanism is actually:

> **false-reversal / premature runner exit**, not simply late trailing after a final peak.

Examples of premature runner close followed by later higher archived peak:

- AVAAI: close around +1.96%, later archived peak +4.11%;
- COMP: close around +1.43%, later archived peak +2.79%;
- FLOW: close around +1.31%, later archived peak +2.93%;
- US: close around +5.42%, later archived peak +7.45%.

These later peaks are retrospective opportunity labels only; once the simulated V4.2 close occurs, the live system would no longer have that position open.

## Finding 6 — Small partial reduce behaves differently

V4.2 fired a small REDUCE25 on **49 trades**:

- **36** occurred after the highest archived observed peak;
- **13** occurred before a later higher peak.

For the 37 Stage3A `PARTIAL_REDUCE_DRAG` failures:

- **31** small reductions occurred after the final peak;
- **6** occurred before a later higher peak.

This supports keeping the small-profit problem separate from the runner problem:

- small/medium profit needs stronger lock architecture after a genuine giveback;
- runner protection primarily needs better transient-vs-final reversal recognition.

## Stage3B decision

Proceed to:

> **PP V4-3C — Temporal Reversal Detector**

Do **not** implement a fixed 80% trailing stop.

Stage3C should test whether a causal combination of:

- peak regime,
- age since last running high,
- downward velocity,
- and reclaim behavior

can distinguish transient pullbacks from final reversals early enough to preserve approximately 80% of the running opportunity **without prematurely killing continuations**.

Stage3C must keep true clean MFE and future-new-high labels strictly as research targets, never runtime features.

No prospective/paper validation yet. No runtime change. No protection authority.
