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

### Stage 2B — Causal Peak Detector Replay
Build a stateful causal detector beginning at the first post-record-peak retracement. The primary objective is to distinguish recovery/continuation from persistent terminal decay before the 20% giveback boundary where possible. Future labels, future maxima, and true MFE are prohibited as inputs.

### Stage 2C — Partial Protect / Runner Frontier
Only after Stage 2B establishes a causal terminal-peak signal, test partial-protection quantity and runner preservation. The split fraction is a research variable, not a fixed 50/50 assumption.

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

Frozen dataset:
- start: `1790848801393`
- cutoff: `1791021852690`

No Stage 1 or Stage 2A research code is imported by production runtime.
