# PP-DECISION V3 — Peak Capture Engineering

Status: **RESEARCH / SHADOW DEVELOPMENT ONLY**

PP-DECISION V3 is a new profit-protection research line built around an explicit economic objective:

> Retain as much as possible of the favorable excursion after a trade becomes meaningfully profitable, with an aspirational portfolio target of approximately 80% peak capture.

The target is an engineering objective, not an assumption that future peak is known in real time.

## Authority

- actual paper authority remains **PP-LEGACY V3**;
- PP-DECISION V2 remains an active comparator / research shadow;
- PP-DECISION V3 has **no paper or live trading authority**.

## Core definitions

- **True MFE**: maximum favorable excursion reconstructed from lifecycle high/low history. This can include intrapoll highs.
- **Observable peak**: maximum current PnL actually seen by the fast polling loop.
- **Capture ratio**: realized/counterfactual PnL relative to a defined peak benchmark.
- **Arm threshold**: initial research threshold of +0.30%.

True MFE may be useful as an offline label/benchmark but must never be used as future information in a live decision.

## Roadmap

### Stage 1 — Capture Frontier ✅ COMPLETE
Test static trailing floors at 50/60/70/75/80/85/90% of causal running observable peak, with diagnostic extension to 92.5/95/97.5%.

Result:
- frozen dataset: 3,234 closed trades;
- 2,210 reached true MFE >= +0.30%;
- only 1,384 were actually observed with current PnL >= +0.30%;
- median observable peak / true MFE: 78.27%;
- weighted observable peak / true peak: 68.38%;
- static 80% floor captured only 27.28% of eventual true peak under polling;
- static 90% floor captured only 28.35%;
- static rules improved net on early/middle cohorts but lost against actual control in the late cohort;
- no static ratio qualifies for promotion.

Main blockers identified:
1. observability gap;
2. premature exit of future runners;
3. poll/execution latency.

Full report:
`docs/research/profit_protection_v3/PP_V3_STAGE1_CAPTURE_FRONTIER.md`

### Stage 2A — Peak / Continuation Anatomy ✅ COMPLETE
Extract record-local observed peaks and retrospectively label them as CONTINUED versus TERMINAL without granting those labels any runtime authority.

Result:
- 5,033 record-local-peak candidates across the frozen observable-arm cohort;
- 3,837 CONTINUED and 1,196 clean TERMINAL candidates;
- terminal observed peak / true MFE: 90.17% median and 88.28% notional-weighted;
- 74.33% of clean terminal observed peaks reached at least 80% of true MFE;
- median terminal giveback: 18.78% at T+15s and 24.32% at T+30s;
- simple giveback/flow rules do not have adequate precision/recall;
- no production authority is granted.

Full report:
`docs/research/profit_protection_v3/PP_V3_STAGE2A_PEAK_CONTINUATION_ANATOMY.md`

### Stage 2B — Causal Peak Detector Replay ✅ COMPLETE — NO PROMOTION
Replay stateful causal detectors from the first post-record-peak retracement and test whether recovery/continuation can be separated from terminal decay before the 20% giveback boundary.

Result:
- 38.04% of terminal candidates are already beyond 20% giveback at the first post-peak poll;
- 171 stateful causal configurations were tested;
- the lowest continued false-exit rate in that grid was still 29.92%;
- the configuration with maximum within-20 terminal recall reached only 37.37% while falsely exiting 52.46% of continued candidates;
- chronological safe-window late-test AUC was 0.5867 with giveback included;
- context-only safe-window late-test AUC was 0.5104;
- no detector qualifies for promotion.

Full report:
`docs/research/profit_protection_v3/PP_V3_STAGE2B_CAUSAL_PEAK_DETECTOR.md`

### Stage 2B.1 — Fast Peak Observation Lane 🔒 RETIRED / ARCHIVED
The dedicated 5-second ticker-only shadow observer ran prospectively and was retired on **2026-10-03** before opening the next research track.

Frozen retirement snapshot:
- activation boundary: `1791030303648`
- first persisted observation: `1791030389337`
- final persisted observation: `1791043570111`
- rows: **54,940**
- distinct positions: **208**
- threshold-crossed rows: **30,386**
- Stage 12 fast guard remained **15 seconds** throughout.

The historical table `pp_v3_fast_peak_observations` is preserved, but the Stage 2B.1 startup loop, read API endpoint, and runtime configuration have been removed from the active path.

Archive manifest:
`research/profit_protection_v3/archive/stage2b1_5s_shadow/ARCHIVE.md`

### Low-Tail Compression Track — 🔒 ARCHIVED / CLOSED / REJECTED

This 15-second Low-Tail track is frozen for audit/reproducibility and must not be continued by retuning the same selector/trailing mechanism. The Stage 2A median of ~90% hid a material lower tail; Stages A–C established that the 15s mechanism could not compress it without runner damage. Reopening requires a materially different information/execution mechanism.

Archive manifest: `research/profit_protection_v3/archive/low_tail_15s/ARCHIVE.md`

#### Stage A — Low-Tail Anatomy ✅ COMPLETE

Frozen 1,196 clean terminal trades were split by terminal observed peak / true MFE.

Result:
- mean capture: **86.33%**
- median capture: **90.17%**
- <90%: **593 / 1,196 = 49.58%**
- <80%: **307 / 1,196 = 25.67%**
- **306 / 307 = 99.67%** of the <80% cohort are intrapoll-excursion dominant;
- median fast cadence is effectively identical: 14.9975s low-tail vs 14.9970s good 90–100%;
- low-tail hidden MFE gap is ~4.9x larger;
- low-tail MFE jump is ~3.6x larger;
- low-tail peak occurs much earlier (median 187s vs 884s for good 90–100%).

Conclusion:
the dominant low-tail mechanism is favorable excursion occurring between ~15-second current-price samples. A later current-ticker detector cannot recover a spike that has already disappeared.

Stage B must test causal pre-arm evidence and conservative exchange-side trailing/conditional capture feasibility using the existing frozen data. Candle high/low may prove trigger-touch feasibility but may not be treated as an exact executable peak fill.

Full report:
`docs/research/profit_protection_v3/archive/low_tail_15s/PP_V3_LOW_TAIL_STAGE_A.md`

#### Stage B — Pre-Arm Detector + Exchange-Side Replay ✅ COMPLETE — NO PROMOTION

B1 used chronological holdout on <80% LOW-TAIL versus 90–100% GOOD trades.

Key fixed-checkpoint result:
- T+30s context late-test AUC: **0.7105**
- T+30s at stricter threshold: recall **25.32%**, good false-positive **6.15%**, precision **62.50%**
- T+60s AUC ~0.55 and T+120s AUC ~0.60
- oracle-timed last causal pre-spike path diagnostic reached AUC **0.8577**, showing useful local information exists but timing remains unresolved.

B2 replayed fully post-entry 1m bars with conservative same-bar ordering and 2 bps slippage.

Result:
- universal native exchange trailing is rejected;
- best conservative native grid result reached only **5.02%** of trades at >=90% capture;
- even idealized 95%-of-excursion trailing reached only **24.16%** >=90% capture;
- the reason is runner destruction: **68–73%** of triggered trades in the best conservative variants exited before final MFE discovery.

Conclusion:
the low-tail can be partially predicted early, but tight protection cannot be applied universally. Stage C must combine selective low-tail risk gating with runner preservation.

Full report:
`docs/research/profit_protection_v3/archive/low_tail_15s/PP_V3_LOW_TAIL_STAGE_B.md`

#### Stage C — Selective Protection + Runner Preservation ✅ COMPLETE — REJECTED

Stage C combined chronological low-tail selection with selective exchange-side protection.

Method:
- EARLY 398 train;
- MID 398 tuning;
- LATE 400 untouched test;
- 1,536 selector × runner-escape × protection combinations.

MID frontier:
- only **5 / 1,536** increased >=90% share;
- **0 / 1,536** reduced the <80% tail;
- **0** did both;
- **0** passed all distribution + runner-preservation gates.

Safest candidate carried to untouched LATE:
- T30/T45/T60 path selector;
- 5% train FPR cap;
- native activation +1.00%, callback 0.10%.

LATE:
- >=90% share: **56.75% → 56.25%**
- <80% share: **22.25% → 23.00%**
- mean capture: **87.06% → 86.68%**
- P10: **67.18% → 65.42%**
- P25: **83.06% → 82.25%**
- low-tail rescued to >=80%: **0%**
- baseline >=90% trades destroyed below90%: **1.32%**

Conclusion:
with the frozen ~15-second observation path and conservative post-selection 1m exchange replay, selective protection still cannot compress the lower tail. **Stage D is blocked** because Stage C produced no qualifying policy.

A materially different information/execution mechanism is required before reopening the track.

Full report:
`docs/research/profit_protection_v3/archive/low_tail_15s/PP_V3_LOW_TAIL_STAGE_C.md`

### Stage 2C — Partial Protect / Runner Frontier ⛔ BLOCKED
Partial-protection quantity and runner preservation remain blocked. Stage 2B.1 is retired; reopening requires a new causal information/execution mechanism that establishes materially better terminal-peak evidence. The split fraction remains a research variable, not a fixed 50/50 assumption.

### Stage 3 — Decay-Aware Protection
Use causal decay/velocity/recovery evidence to distinguish a temporary retracement from genuine profit failure.

### Stage 4 — Runner Escape
Give continuing runners a mechanism to ratchet without being killed by the same floor used for smaller peaks.

### Stage 5 — Causal Replay
Evaluate the combined policy against full fast-observation streams with fees/slippage and strict chronological validation.

### Stage 6 — Prospective Shadow
Run a clean new cohort as observation/shadow only. Promotion requires prospective evidence.

## Frozen research artifacts

### Stage 1
- replay script: `research/profit_protection_v3/stage1_capture_frontier.py`
- frozen result JSON: `research/profit_protection_v3/results/stage1_capture_frontier_1791021852690.json`
- unit tests: `tests/test_pp_v3_stage1_capture_frontier.py`

### Stage 2A
- anatomy script: `research/profit_protection_v3/stage2a_peak_continuation_anatomy.py`
- frozen result JSON: `research/profit_protection_v3/results/stage2a_peak_continuation_anatomy_1791021852690.json`
- unit tests: `tests/test_pp_v3_stage2a_peak_continuation_anatomy.py`

### Stage 2B
- causal replay: `research/profit_protection_v3/stage2b_causal_peak_detector.py`
- frozen result JSON: `research/profit_protection_v3/results/stage2b_causal_peak_detector_1791021852690.json`
- unit tests: `tests/test_pp_v3_stage2b_causal_peak_detector.py`

### Stage 2B.1 (archived)
- manifest: `research/profit_protection_v3/archive/stage2b1_5s_shadow/ARCHIVE.md`
- observer: `research/profit_protection_v3/archive/stage2b1_5s_shadow/profit_protection_v3_fast_observer.py`
- contract: `docs/research/profit_protection_v3/archive/stage2b1_5s_shadow/PP_V3_STAGE2B1_FAST_PEAK_OBSERVATION.md`
- tests: `research/profit_protection_v3/archive/stage2b1_5s_shadow/tests/test_fast_peak_observer.py`
- activation boundary: `1791030303648`
- first observation: `1791030389337`
- last observation: `1791043570111`
- final rows: **54,940** across **208** positions

### Low-Tail 15s Archive
- manifest: `research/profit_protection_v3/archive/low_tail_15s/ARCHIVE.md`

### Low-Tail Stage A (archived)
- anatomy script: `research/profit_protection_v3/archive/low_tail_15s/stage_a_low_tail_anatomy.py`
- frozen result: `research/profit_protection_v3/archive/low_tail_15s/results/stage_a_low_tail_anatomy_1791021852690.json`
- report: `docs/research/profit_protection_v3/archive/low_tail_15s/PP_V3_LOW_TAIL_STAGE_A.md`
- tests: `research/profit_protection_v3/archive/low_tail_15s/tests/test_stage_a.py`

### Low-Tail Stage B (archived)
- replay script: `research/profit_protection_v3/archive/low_tail_15s/stage_b_low_tail_prearm_exchange.py`
- frozen result: `research/profit_protection_v3/archive/low_tail_15s/results/stage_b_low_tail_prearm_exchange_1791021852690.json`
- report: `docs/research/profit_protection_v3/archive/low_tail_15s/PP_V3_LOW_TAIL_STAGE_B.md`
- tests: `research/profit_protection_v3/archive/low_tail_15s/tests/test_stage_b.py`

### Low-Tail Stage C (archived)
- replay script: `research/profit_protection_v3/archive/low_tail_15s/stage_c_selective_protection.py`
- frozen result: `research/profit_protection_v3/archive/low_tail_15s/results/stage_c_selective_protection_1791021852690.json`
- report: `docs/research/profit_protection_v3/archive/low_tail_15s/PP_V3_LOW_TAIL_STAGE_C.md`
- tests: `research/profit_protection_v3/archive/low_tail_15s/tests/test_stage_c.py`

Frozen dataset:
- start: `1790848801393`
- cutoff: `1791021852690`

Stage 1, Stage 2A, and Stage 2B replay code is not imported by production runtime. Stage 2B.1 is archived and no longer has active runtime wiring or trading authority.
