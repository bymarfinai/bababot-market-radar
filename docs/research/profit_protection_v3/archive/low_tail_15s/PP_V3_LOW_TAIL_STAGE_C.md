> **ARCHIVED / CLOSED / REJECTED TRACK** — retained for reproducibility. Do not continue tuning this 15s low-tail branch in the active research path.\n\n# PP-DECISION V3 — Low-Tail Stage C Selective Protection

Status: **COMPLETE — NO PROMOTION**

## Objective

Stage B showed two facts:

1. low-tail risk is partially predictable early;
2. universal tight trailing destroys too many future runners.

Stage C tests the combined hypothesis:

> Activate tight protection only on trades selected as high low-tail risk, while leaving non-selected trades on the runner-preservation path.

The stage uses only the existing frozen historical cohort. No prospective data is required.

## Frozen baseline

Clean terminal cohort:

- trades: **1,196**
- mean terminal observed peak / true MFE: **86.33%**
- median: **90.17%**
- P10: **67.99%**
- P25: **79.48%**
- >=90% share: **50.42%**
- <80% share: **25.67%**

## Chronological methodology

The 1,196 terminal trades are ordered by open time and split:

- EARLY train: **398**
- MID tuning: **398**
- LATE untouched test: **400**

The selector is trained only on LOW-TAIL (<80%) versus GOOD (90–100%) labels.

Candidate selector state windows:

- T30 only
- T30/T45/T60
- T30/T45/T60/T75/T90
- T30 through T120

Feature families:

- context features
- context + causal path features

Trade-level false-positive caps:

- 5%
- 10%
- 15%
- 20%

Runner escape options:

- none
- causal running current-PnL peak >=0.75%
- >=1.00%
- >=1.50%

Protection grid:

- native price-callback trails at activation 0.30/0.50/0.75/1.00% with 0.10/0.20% callback;
- idealized excursion-retention trails at activation 0.30/0.50% with 90/95% retention.

Total MID tuning combinations:

**1,536**

## Execution guardrails

Stage C remains conservative:

- protection may begin only after a causal selector observation;
- only full 1-minute bars whose open time is after the selection timestamp are eligible;
- the bar containing the selection timestamp is excluded;
- if activation/new peak and stop crossing occur inside the same 1-minute bar, ordering is unknown and no exit is assumed;
- 2 bps adverse exit slippage is retained from Stage B.

The Stage C hybrid distribution is a research opportunity metric:

- unselected trades keep their Stage A terminal observed-peak benchmark;
- selected trades keep that benchmark if protection never triggers;
- if selected protection triggers, the numerator is replaced by the conservative replay exit.

This explicitly counts runner destruction: once selected protection exits, the trade cannot later reclaim the Stage A terminal benchmark.

It is not a full realized-PnL backtest.

## MID tuning frontier

The grid result is decisive.

Across **1,536 candidates**:

- candidates that increased >=90% share: **5**
- candidates that reduced <80% share: **0**
- candidates that did both: **0**
- candidates passing every Stage C tuning gate: **0**

The best candidate solely by >=90% uplift was:

- selector: T30-only path features
- train FPR cap: 10%
- no runner-escape gate
- protection: ideal activation +0.50%, retain 95%

MID result versus its own baseline:

- >=90% share: **+0.25 percentage point**
- <80% share: **+2.51 pp** — worse
- mean capture: **-1.46 pp**
- P10: **-5.64 pp**
- P25: **-1.12 pp**
- good >=90% trades destroyed below 90%: **6.52%**
- baseline low-tail rescued to >=80%: **5.50%**

So even the candidate with positive top-end movement creates materially more new low-tail than it rescues.

The candidate with the smallest <80% damage still did not reduce the tail:

- >=90% share: **-0.75 pp**
- <80% share: **+0.50 pp**
- mean: **-0.28 pp**
- runner damage: **2.17%**

There is no hidden MID configuration that solves the tradeoff.

## Selected conservative candidate for untouched LATE test

Because no candidate passed all tuning gates, Stage C carries the safest non-degrading candidate to LATE as a falsification check:

- window: T30/T45/T60
- path features
- train FPR cap: 5%
- no runner-escape threshold
- native activation +1.00%, callback 0.10%

The model is refit on EARLY + MID using the frozen configuration, then evaluated once on LATE.

### LATE selector behavior

- LATE trades: **400**
- labeled LOW-TAIL: **89**
- labeled GOOD: **201**
- selected labeled trades: **16**
- low-tail precision: **56.25%**
- low-tail recall: **10.11%**
- good false-positive rate: **3.48%**
- total selected positions: **19**
- definite protection triggers: **6**

### LATE distribution

Baseline LATE:

- >=90%: **56.75%**
- <80%: **22.25%**
- mean: **87.06%**
- median: **91.84%**
- P10: **67.18%**
- P25: **83.06%**

Selective Stage C result:

- >=90%: **56.25%**
- <80%: **23.00%**
- mean: **86.68%**
- median: **91.62%**
- P10: **65.42%**
- P25: **82.25%**

Delta:

- >=90%: **-0.50 pp**
- <80%: **+0.75 pp**
- mean: **-0.38 pp**
- median: **-0.22 pp**
- P10: **-1.76 pp**
- P25: **-0.81 pp**

Additional diagnostics:

- baseline LOW-TAIL rescued to >=80%: **0%**
- baseline LOW-TAIL rescued to >=90%: **0%**
- baseline >=90% trades destroyed below90%: **1.32%**
- among selected trades, trigger rate: **31.58%**
- 50% of triggered exits occurred before final MFE discovery.

## Why selective protection still fails

Stage C removes most of the universal-trailing damage, but it does not reverse the low-tail distribution.

Two problems remain.

### 1. Selection recall is too low at safe false-positive rates

The late selector is reasonably precise but only captures about **10%** of low-tail trades.

Increasing selection aggressiveness creates more false positives and therefore more runner destruction.

### 2. The intervention is still too late / too coarse

The dominant Stage A problem is a favorable excursion occurring between ~15-second observations.

Stage C can select only after a causal observation and then conservatively starts exchange replay on the next fully post-selection 1-minute bar.

For the LATE cohort, **none** of the baseline <80% trades were rescued to >=80%.

This is direct evidence that the current historical observation/replay resolution cannot turn the early classifier signal into a reliable >=90% capture intervention.

## Stage C conclusion

**Stage C is complete and rejected for promotion.**

The result is stronger than "the chosen threshold was bad":

> Across 1,536 selector/protection combinations, zero configurations reduced the <80% tail on MID, and zero passed the combined distribution + runner-preservation gates.

The untouched LATE test confirms the failure:

- >=90% share falls;
- <80% share rises;
- P10/P25 worsen;
- no low-tail trade is rescued.

Therefore the Stage A–C frozen 15-second research path has reached a practical information/timing boundary.

## Stage D status

The originally planned Stage D full-policy replay is **BLOCKED** for this branch because Stage C produced no qualifying policy to replay.

Running a final replay of a rejected Stage C policy would not create new evidence; Stage C already includes an untouched chronological LATE test.

A future branch must materially change the information/execution mechanism before reopening Stage D, for example:

- sub-15-second / event-driven causal state;
- earlier exchange-side arming before the intrapoll excursion;
- richer tick/order-book path evidence;
- another mechanism that does not require recognizing the spike after it has already disappeared.

No production threshold, paper authority, or live authority is changed.

## Reproducibility

- script: `research/profit_protection_v3/archive/low_tail_15s/stage_c_selective_protection.py`
- frozen result: `research/profit_protection_v3/archive/low_tail_15s/results/stage_c_selective_protection_1791021852690.json`
- tests: `research/profit_protection_v3/archive/low_tail_15s/tests/test_stage_c.py`
