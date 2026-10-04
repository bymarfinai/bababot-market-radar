# PP V4-1I — 5s Failure Anatomy

Status: **COMPLETE — RESEARCH ONLY**

## Question

Why do trades remain below 80% capture under the archived ~5-second current-price observer?

## Critical benchmark finding

Stage 12 fast lifecycle MFE is reconstructed from `rolling_1m_high` / `rolling_1m_low` inside `_build_fast_snapshot`, then accumulated by `_mfe_mae`.

That rolling closed-bar window is **not clipped to the position entry time**.

For newly opened positions, the MFE path can therefore inherit favorable candle extrema that occurred **before the position was opened**.

This means some historical "true MFE" labels were not valid post-entry opportunity labels.

## Population

Stage1H apparent 5s low-tail:
- **53 trades** with archived 5s capture <80%.

After reconstructing actual traded-price MFE strictly after entry using Binance aggregate trades for partial boundary minutes plus 1m klines for full in-lifecycle minutes:

- actual post-entry MFE >=0.30%: **28**
- actual post-entry MFE <0.30%: **25**
- genuine corrected 5s capture <80%: **24**

## Failure decomposition

| Category | N | Share |
|---|---:|---:|
| False MFE eligibility: actual post-entry MFE <0.30% | **25** | **47.17%** |
| Benchmark contamination dominant; corrected capture >=80% | **4** | **7.55%** |
| Mixed contamination + genuine 5s miss | **4** | **7.55%** |
| Clean genuine post-entry 5s miss | **20** | **37.74%** |

So **29 / 53 = 54.72%** of the apparent 5s failures are invalidated or resolved primarily by correcting the benchmark.

Among trades with positive actual post-entry favorable excursion:
- lifecycle MFE > actual post-entry MFE by >10%: **29**
- >25%: **27**
- >2x: **25**

## Corrected apparent low-tail

Among the 28 trades that truly reached post-entry MFE >=0.30%:

- corrected capture <80%: **24**
- corrected capture >=80%: **4**
- corrected capture >=90%: **2**
- old apparent-low-tail median capture: **16.78%**
- corrected median capture: **61.52%**
- corrected P10: **18.29%**
- corrected P25: **43.57%**

## Genuine residual mechanism

The 24 genuine residual misses were checked against actual Binance aggregate-trade timing around the real post-entry peak.

Time spent at >=90% of actual post-entry MFE:

- median longest consecutive run: **1 second**
- P90 longest run: **2 seconds**
- <5 seconds: **24 / 24**
- <=2 seconds: **23 / 24**

Persistence classes:
- **20 / 24 = 83.33%**: peak region <=1 second
- **3 / 24 = 12.50%**: about 2 seconds
- **1 / 24 = 4.17%**: 3–4 seconds
- **0 / 24**: >=5 seconds

Median timing around the true peak:
- nearest 5s observation before peak: **2,824.5 ms**
- nearest 5s observation after peak: **2,191 ms**

Therefore the remaining valid failures are genuine **sub-5s flash excursions**.

## Interpretation

Two separate problems were previously mixed together:

1. **MFE benchmark contamination**
   - pre-entry candle extrema can be inherited by Stage12 MFE;
   - this created false profit opportunities and exaggerated capture failure.

2. **Real sub-5s observability loss**
   - after benchmark correction, 24 genuine misses remain;
   - every one spent <5 consecutive seconds at >=90% of actual post-entry MFE;
   - 20/24 lasted <=1 second.

## Decision

Stage1H remains useful as directional evidence that 5s current-price observation is better than ~15s, but its **MFE-based promotion gates are partially superseded** until MFE labels are rebuilt with a strict entry boundary.

Immediate next priority:

> **Fix Stage12 MFE entry-boundary handling and rebuild clean post-entry MFE labels.**

Only after the benchmark is corrected should we rerun:
- 5s vs 15s;
- lower-tail distribution;
- P10/P25;
- then, if residual flash misses persist, test 1s/2s/event-driven observation.

Do **not** tune profit-protection formulas against the contaminated historical MFE benchmark.

## Frozen artifacts

- analysis: `research/profit_protection_v4/stage1i_5s_failure_anatomy.py`
- result: `research/profit_protection_v4/results/stage1i_5s_failure_anatomy.json`
- post-entry extrema evidence: `research/profit_protection_v4/results/stage1i_low_tail_post_entry_tick_evidence.json`
- residual persistence evidence: `research/profit_protection_v4/results/stage1i_residual_peak_persistence_evidence.json`
