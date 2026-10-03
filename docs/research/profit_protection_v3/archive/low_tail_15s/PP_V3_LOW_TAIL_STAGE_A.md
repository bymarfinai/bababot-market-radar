> **ARCHIVED / CLOSED / REJECTED TRACK** — retained for reproducibility. Do not continue tuning this 15s low-tail branch in the active research path.\n\n# PP-DECISION V3 — Low-Tail Stage A Anatomy

Status: **COMPLETE — frozen historical anatomy, no production authority**

## Objective

The low-tail compression track asks a stricter question than the earlier median/mean analysis:

> Why do some clean terminal trades observe less than 90% of true MFE, and especially less than 80%, while other trades observe 90–100%?

The engineering goal is not to hide or discard the low tail. The goal is to identify the mechanism that creates it so later stages can test whether it can be reduced causally.

Stage A uses the existing frozen Stage 2A cohort only. No new prospective data is required for this anatomy.

## Frozen cohort

- start boundary: `1790848801393`
- cutoff: `1791021852690`
- arm threshold: +0.30%
- clean terminal trades: **1,196**
- source of executable observations: `pp_decision_v2_observations.current_pnl_pct`
- offline benchmark: lifecycle / PP-V2 MFE reconstruction

Distribution of terminal observed peak / true MFE:

- mean: **86.33%**
- median: **90.17%**
- P10: **67.99%**
- P25: **79.48%**
- P75: **96.63%**
- >=90%: **603 / 1,196 = 50.42%**
- <90%: **593 / 1,196 = 49.58%**
- <80%: **307 / 1,196 = 25.67%**
- >100%: **69 / 1,196 = 5.77%**

The >100% bucket is almost entirely numerical / benchmark synchronization around 100%. Only two trades exceed 101%, so it is not the source of the low-tail problem.

## Low-tail bands

| Capture band | Trades | Share |
|---|---:|---:|
| <50% | 28 | 2.34% |
| 50–60% | 41 | 3.43% |
| 60–70% | 65 | 5.43% |
| 70–80% | 173 | 14.46% |
| 80–90% | 286 | 23.91% |
| 90–100% | 534 | 44.65% |
| 100–105% | 68 | 5.69% |
| >105% | 1 | 0.08% |

The severe <70% bucket contains **134 trades (11.20%)**.

## Dominant finding: low tail is an intrapoll-excursion problem

Among the **307 trades below 80%**:

- **306 / 307 = 99.67%** are classified as **INTRAPOLL_EXCURSION_DOMINANT**;
- 1 trade is a benchmark-stream mismatch.

Meaning:

1. the fast lifecycle MFE/candle reconstruction did see a much larger favorable excursion;
2. the current ticker observations did not sample near that excursion;
3. therefore the low capture ratio is primarily caused by favorable movement occurring between executable current-price polls.

This is not explained by slower polling in the low-tail cohort.

Median per-trade fast cadence:

- <80% cohort: **14.9975 s**
- 90–100% cohort: **14.9970 s**

The cadence is effectively identical.

## <80% versus 90–100%

| Metric | <80% low tail | 90–100% good |
|---|---:|---:|
| Trades | 307 | 534 |
| Mean capture | **67.82%** | **95.58%** |
| Median capture | **71.50%** | **95.61%** |
| Median true MFE | 0.775% | 1.066% |
| Median hidden MFE gap | **0.237 pp** | **0.048 pp** |
| Median MFE jump | **0.306 pp** | **0.085 pp** |
| Median latest 1m range | **0.456%** | **0.306%** |
| Median terminal-peak age | **187 s** | **884 s** |
| Median total trade duration | **397 s** | **1,443 s** |
| LONG share | 52.77% | 63.48% |
| Flow aligned at terminal peak | 63.52% | 61.42% |
| Flow opposite at terminal peak | 16.61% | 20.41% |

The hidden MFE gap is about **4.9x larger** in the <80% cohort.

The MFE jump is about **3.6x larger**.

The latest 1m range is about **49% larger**.

The low-tail peak also occurs much earlier:

- median terminal-peak age <80%: **3.1 minutes**
- median terminal-peak age 90–100%: **14.7 minutes**

Low-tail trades are therefore typically **shorter, earlier, and more spike-like**.

## Severity gradient

The pattern strengthens as capture gets worse.

### Severe <70%

- trades: **134**
- median capture: **59.49%**
- median MFE jump: **0.476 pp**
- median latest 1m range: **0.498%**
- median terminal-peak age: **141 s**
- median total duration: **292 s**

### 70–80%

- trades: **173**
- median capture: **75.55%**
- median MFE jump: **0.237 pp**
- median latest 1m range: **0.438%**
- median terminal-peak age: **251 s**

### 80–90%

- trades: **286**
- median capture: **85.55%**
- median MFE jump: **0.165 pp**
- median latest 1m range: **0.409%**
- median terminal-peak age: **348 s**

### 90–100%

- trades: **534**
- median capture: **95.61%**
- median MFE jump: **0.085 pp**
- median latest 1m range: **0.306%**
- median terminal-peak age: **884 s**

There is a clear monotonic anatomy: the worse the observed capture, the larger and earlier the hidden MFE jump.

## Context features do not explain the low tail by themselves

At the terminal observed peak:

- flow-aligned is **63.52%** for <80% versus **61.42%** for good 90–100%;
- flow-opposite is **16.61%** versus **20.41%**;
- opposite micro-structure is nearly absent in both cohorts;
- positioning-opposite is sparse in both cohorts.

So the existing flow / structure / positioning flags are not the dominant cause of the observability miss.

Side shows some skew:

- <80% LONG share: **52.77%**
- good 90–100% LONG share: **63.48%**

SHORT positions are somewhat overrepresented in the low tail, but side alone cannot explain a 25.67% portfolio-wide low-tail rate.

## Chronological robustness

The low-tail problem exists across the entire frozen window:

| Third | Mean capture | Median capture | <80% share | <90% share |
|---|---:|---:|---:|---:|
| EARLY | 86.09% | 89.52% | 27.39% | 51.76% |
| MID | 85.86% | 88.94% | 27.32% | 53.88% |
| LATE | 87.06% | 91.84% | 22.31% | 43.11% |

The late cohort improves, but more than one in five terminal trades is still below 80%.

This is not an isolated early-data artifact.

## Symbol diagnostics

A few symbols have repeated low-tail observations, for example:

- PUMPBTCUSDT: 6/6 below 80%
- GTCUSDT: 6/7 below 80%
- ZKCUSDT: 3/3 below 80%

However, symbol sample counts are small and should not be promoted into exclusions without chronological validation. Stage A treats them only as diagnostics.

## What Stage A changes

The original hypothesis was that Stage B should mainly learn a better low-tail classifier from the 15-second snapshots.

Stage A shows that this is incomplete.

For **306 of the 307 <80% trades**, the favorable excursion is already present in the MFE/candle path but is missed by the sampled current ticker.

Therefore:

> A classifier that only reacts after a 15-second current-price observation cannot recover a price excursion that has already happened and disappeared between polls.

This does not prove that >=90% capture is impossible. It identifies the mechanism that Stage B must target.

## Stage B implication

Stage B should test two distinct existing-data paths:

1. **Causal pre-arm detector**
   - Can pre-spike information identify trades likely to produce a short-lived favorable excursion?
   - The detector may use only information available before the excursion.

2. **Exchange-side capture feasibility**
   - If a position is already armed before the spike, could an exchange-native trailing / conditional protection mechanism have reacted inside the polling interval?
   - Historical candle high/low may be used only to establish whether a trigger price was touched.
   - Replay must be conservative about fill price and intra-candle ordering; it may not assume an exit exactly at the offline peak.

This is materially different from simply lowering a trailing threshold in the bot's 15-second loop.

## Stage A conclusion

**Stage A is complete.**

The low-tail problem is highly concentrated and mechanically interpretable:

> **The dominant source of <80% capture is short-lived favorable excursion occurring between ~15-second current-price samples.**

Key frozen facts:

- 307 / 1,196 terminal trades are <80%;
- 306 / 307 of those are intrapoll-excursion dominant;
- low-tail polling cadence is not slower than good trades;
- low-tail MFE jumps are ~3.6x larger;
- low-tail hidden MFE gaps are ~4.9x larger;
- low-tail peaks happen much earlier and trades finish much faster.

Stage B must therefore test whether the system can **arm before the spike and/or delegate sub-poll protection to the exchange**, rather than pretending a later ticker snapshot can recover a vanished peak.

No production threshold or authority is changed by Stage A.

## Reproducibility

- script: `research/profit_protection_v3/archive/low_tail_15s/stage_a_low_tail_anatomy.py`
- frozen result: `research/profit_protection_v3/archive/low_tail_15s/results/stage_a_low_tail_anatomy_1791021852690.json`
- tests: `research/profit_protection_v3/archive/low_tail_15s/tests/test_stage_a.py`
