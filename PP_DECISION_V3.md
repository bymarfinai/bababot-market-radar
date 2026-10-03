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

### Stage 2 — Dynamic Floor
Engineer floor strength as a state-dependent function instead of one static percentage. Must explicitly protect runner continuation and cannot use future MFE.

### Stage 3 — Decay-Aware Protection
Use causal decay/velocity/recovery evidence to distinguish a temporary retracement from genuine profit failure.

### Stage 4 — Runner Escape
Give continuing runners a mechanism to ratchet without being killed by the same floor used for smaller peaks.

### Stage 5 — Causal Replay
Evaluate the combined policy against full fast-observation streams with fees/slippage and strict chronological validation.

### Stage 6 — Prospective Shadow
Run a clean new cohort as observation/shadow only. Promotion requires prospective evidence.

## Stage 1 frozen artifacts

- replay script: `research/profit_protection_v3/stage1_capture_frontier.py`
- frozen result JSON: `research/profit_protection_v3/results/stage1_capture_frontier_1791021852690.json`
- unit tests: `tests/test_pp_v3_stage1_capture_frontier.py`
- dataset start: `1790848801393`
- dataset cutoff: `1791021852690`

No Stage 1 code is imported by production runtime.
