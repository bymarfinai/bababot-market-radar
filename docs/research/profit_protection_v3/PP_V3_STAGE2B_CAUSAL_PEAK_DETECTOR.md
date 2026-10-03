# PP-DECISION V3 — Stage 2B Causal Peak Detector Replay

Status: **COMPLETE — research replay only, NO PROMOTION**

## Objective

Stage 2A showed that clean terminal observed peaks are often close to true MFE, but the economic window after the peak is narrow.

Stage 2B tests whether a causal detector can identify terminal peaks early enough to preserve roughly 80% of the observed peak while avoiding premature exits from trades that later continue to a higher peak.

No production runtime, PP-LEGACY V3 authority, PP-DECISION V2 shadow authority, paper execution, or live execution is changed.

## Frozen dataset

Stage 2B reuses the same frozen window:

- start: `1790848801393`
- cutoff: `1791021852690`
- observable-arm trades: **1,384**
- record-local-peak candidates: **5,033**
- CONTINUED candidates: **3,837**
- TERMINAL candidates: **1,196**
- arm: **+0.30% observed current PnL**

The offline CONTINUED / TERMINAL labels are used only for research evaluation and supervised separability testing. They are never input to the causal detector replay.

## Causal state machine

For each observed record-local peak, the detector sees only information available up to the current observation:

- causal running observed peak;
- current PnL;
- current giveback from candidate peak;
- trough since candidate peak;
- recovery fraction from the trough;
- elapsed poll step;
- flow-aligned / flow-opposite flags;
- current microstructure and positioning flags.

A candidate is immediately cancelled if a later current-PnL observation exceeds the candidate peak. That event is a causal recovery / continuation outcome.

The frozen grid contains **171** interpretable stateful configurations built from:

- optional first-poll hard giveback: none / 20% / 25% / 30%;
- optional any-poll hard giveback: 25% / 30% / 35% / none;
- recovery-failure soft giveback: 10% / 15% / 20%;
- maximum recovery fraction: 0 / 25% / 50%;
- optional requirement that flow is no longer aligned.

## First post-peak poll: the hard timing ceiling

At the first observation after the record peak:

| Metric | Result |
|---|---:|
| TERMINAL median giveback | **14.54%** |
| CONTINUED median giveback | **7.75%** |
| TERMINAL still within 20% giveback | **61.96%** |
| TERMINAL already beyond 20% giveback | **38.04%** |

This creates a hard observability/cadence limitation:

> **38.04% of clean terminal candidates have already violated the 20% giveback budget before the first post-peak fast observation is available.**

A perfect classifier cannot restore 80% observed-peak retention for those events using the current observation cadence.

## Chronological stability of the timing ceiling

| Split | Candidates | Terminal rate | Terminal median first-poll giveback | Terminal still within 20% |
|---|---:|---:|---:|---:|
| EARLY | 1,393 | 28.43% | 15.08% | 60.86% |
| MID | 1,712 | 24.24% | 16.21% | 59.52% |
| LATE | 1,928 | 19.97% | 11.72% | 65.71% |

The exact terminal rate drifts materially, but the core cadence problem remains present across all chronological thirds.

## Stateful rule frontier

The complete 171-rule causal grid fails to find a usable peak detector.

### Lowest runner false-exit configuration

Configuration:

- no first-poll hard trigger;
- no any-poll hard trigger;
- soft giveback >=15%;
- zero recovery from trough;
- require flow not aligned.

Results:

- terminal precision: **48.17%**
- terminal recall: **89.21%**
- continued false-exit rate: **29.92%**
- terminal detected within 20% giveback: **15.47%**
- terminal median giveback at detection: **39.54%**

Critically:

- no tested configuration achieved continued false exits <=10%;
- none achieved <=15%;
- none achieved <=20%;
- none achieved <=25%.

The minimum observed continued false-exit rate in the full grid was **29.92%**.

### Highest within-20 terminal recall configuration

Configuration:

- no hard trigger;
- soft giveback >=10%;
- recovery fraction <=50%;
- no flow-alignment requirement.

Results:

- terminal recall: **98.58%**
- terminal within-20 recall: **37.37%**
- terminal precision: **36.94%**
- continued false-exit rate: **52.46%**
- terminal median giveback at detection: **25.11%**

So improving early terminal coverage destroys runner preservation.

## Chronological model holdout

To test whether the manual state-machine grid was simply too crude, Stage 2B also runs a deterministic logistic separability benchmark:

- first two chronological thirds of eligible positions: training;
- final third: holdout test;
- threshold selected on training data to cap training continued false-exit rate at 10%;
- no future feature is used;
- future terminal labels are used only as offline training/evaluation targets.

### Full first-poll feature set

Features include giveback plus the current causal context.

- train AUC: **0.6479**
- late test AUC: **0.6461**
- late test continued false-exit rate: **5.31%**
- late test terminal recall: **19.48%**
- late test terminal precision: **47.77%**
- late test terminal median giveback when selected: **53.00%**
- terminal-within-20 recall: **0.26%**

The model can become selective, but it mostly becomes confident only after the peak has already been lost.

### Context only, without giveback

- train AUC: **0.5771**
- late test AUC: **0.5424**
- late test terminal recall: **14.03%**
- late test continued false-exit: **7.78%**

The current flow/momentum/microstructure context is weak as an early peak signal.

## Safe-window test: only observations still within 20% giveback

This is the most important diagnostic because it asks the exact economic question:

> While the trade is still inside the 80%-capture tolerance band, can the current causal evidence identify terminal peaks?

Safe-window population:

- training rows: **2,292**
- training terminal: **488**
- late-test rows: **1,577**
- late-test terminal: **253**

### Safe window — all first-poll features

- train AUC: **0.6059**
- late test AUC: **0.5867**
- late test terminal precision: **25.76%**
- late test terminal recall: **13.44%**
- late test continued false-exit: **7.40%**

### Safe window — context only

- train AUC: **0.5556**
- late test AUC: **0.5104**
- late test terminal precision: **24.24%**
- late test terminal recall: **12.65%**
- late test continued false-exit: **7.55%**

An AUC of **0.5104** on the late cohort is effectively near-random discrimination.

This is the central Stage 2B result:

> **Inside the economically safe <=20% giveback window, the current context features do not contain enough robust terminal-peak information.**

## Interpretation

Stage 2B does not fail because one threshold was chosen incorrectly.

It finds two independent blockers:

1. **Cadence / observability blocker**
   - 38.04% of terminal candidates are already beyond the 20% giveback boundary at the first post-peak observation.

2. **Early-information blocker**
   - among candidates still inside the boundary, the current context-only feature set has almost no late-cohort discrimination.

Waiting for more temporal evidence improves classification, but that evidence arrives after the economic objective has already been violated for many terminal trades.

## Stage 2B conclusion

**NO DETECTOR IS PROMOTED.**

Stage 2C Partial Protect / Runner Frontier remains **BLOCKED** as a production-candidate study because the trigger feeding it is not yet trustworthy enough.

The next problem is not quantity splitting. It is peak observability.

## Next required research — Stage 2B.1 Fast Peak Observation Lane

A clean next experiment should test whether earlier causal evidence fixes the problem:

- 5-second or event-driven current-price observations after a profitable record peak;
- sub-poll giveback velocity;
- recovery micro-path before the existing ~15-second poll;
- richer causal taker / price / OI microstate if available at that cadence;
- prospective shadow only.

The Stage 2B frozen data cannot reconstruct evidence that was never observed, so a sub-15-second detector cannot be honestly backfilled from the current 15-second stream.

## Reproducibility

- script: `research/profit_protection_v3/stage2b_causal_peak_detector.py`
- frozen result: `research/profit_protection_v3/results/stage2b_causal_peak_detector_1791021852690.json`
- tests: `tests/test_pp_v3_stage2b_causal_peak_detector.py`

No Stage 2B code is imported by production runtime.
