# WD-5H Stage 1 VPS Frozen Results — 2026-10-01

Source of truth: VPS `core-prod`.  
Authority: research only.  
Production changes: none.

## Executive conclusion

Formal status:

`DIRECT_BINARY_WEAK_PAIRWISE_STRONG`

The core result is:

> A single flat classifier that tries to distinguish WINNER from every kind of non-winner at once is likely to be inefficient.

But the non-winner classes are not indistinguishable.

When separated by failure type, the entry-state differences become much stronger and more stable.

This strongly supports a hierarchical selective-entry architecture.

---

## Full-population thesis labels

| Thesis class | N | Share | Net PnL | Median MFE |
|---|---:|---:|---:|---:|
| **VALID_WINNER** | **500** | 22.99% | **+$1,387.84** | **1.385%** |
| RIGHT_THEN_FAILURE | 660 | 30.34% | -$746.44 | 0.703% |
| TRUE_WRONG_DIRECTION | 849 | 39.03% | -$2,374.55 | 0.188% |
| STALL_NO_EDGE | 166 | 7.63% | -$605.50 | 0.416% |

VALID_WINNER is composed of:

- 115 clean/correct runners
- 385 recovered-drawdown winners

All 500 are realized positive.

---

## Direct selective target: VALID_WINNER vs ALL NON-WIN

Cohort:

- positive: 500
- negative: 1,675

Only **4 features** pass the strict Stage 1 stability screen across all chronological fifths.

Stable families:

- Stage11C: 1
- micro path: 1
- flow / structure: 2

The stable features include:

- Stage11C family combination
- micro volume-climax/fade behavior
- selected-side 5m taker share
- selected-side 5m taker delta

This is not enough evidence to justify a simple flat high-precision WIN classifier yet.

### Important interpretation

The weakness does **not** mean winners are random.

It means the negative class is heterogeneous:

- some are fundamentally wrong direction,
- some have no edge,
- some have a correct initial thesis but later fail.

Those groups require different rejection logic.

---

## VALID_WINNER vs TRUE_WRONG_DIRECTION

Stable feature count:

**14**

Important stable evidence includes:

- 15m / 30m distance from selected-side local extreme
- Stage11C family combination
- gate side-adjusted drift
- selected-side taker share
- micro taker share
- Stage 5 taker context
- OI interpretation / structure / regime categories

### Local-extreme distance

Median 30m selected-extreme distance:

- VALID_WINNER: ~0.157%
- TRUE_WRONG_DIRECTION: ~0.111%

Median 15m distance:

- VALID_WINNER: ~0.148%
- TRUE_WRONG_DIRECTION: ~0.107%

These features are consistently different across chronological blocks.

This shows that true-wrong entries and valid winners occupy measurably different micro-location states.

---

## VALID_WINNER vs RIGHT_THEN_FAILURE

This is one of the strongest Stage 1 comparisons.

Stable feature count:

**48**

Important feature families:

- micro path
- WD-5D overheat
- Stage11C
- movement
- Stage4 score/components
- Stage5 context
- flow / structure
- market relative

### Local-extreme location

15m distance to selected extreme:

- VALID_WINNER median: **0.148%**
- RIGHT_THEN_FAILURE median: **0.298%**

30m:

- VALID_WINNER: **0.157%**
- RIGHT_THEN_FAILURE: **0.306%**

This is one of the strongest and most stable effects.

### Overheat pressure

- VALID_WINNER median: **4.73**
- RIGHT_THEN_FAILURE median: **6.13**

So lifecycle failures are, on average, entered in a hotter / more extended continuation state.

### Selected score

- VALID_WINNER median: **80.42**
- RIGHT_THEN_FAILURE median: **84.07**

Again, stronger-looking score is not automatically better.

### Activity / trade expansion

RIGHT_THEN_FAILURE generally shows:

- higher activity heat,
- higher trades ratio,
- stronger score x activity heat,
- higher recent selected-side momentum.

This reinforces the WD-5C/5D finding that overextension is a major failure mode.

---

## VALID_WINNER vs STALL_NO_EDGE

Stable feature count:

**29**

Important features include:

- Stage11C family combination
- taker-share / taker-delta support
- selected-side VWAP extension
- Stage 5 taker context
- positioning support
- market-relative residual
- movement expansion

This indicates that STALL/NO_EDGE is a separate entry-quality problem from TRUE_WRONG_DIRECTION.

It should have its own rejection head.

---

## TRUE_WRONG_DIRECTION vs RIGHT_THEN_FAILURE

This is the most important WD-5G follow-up comparison.

Stable feature count:

**61**

The two failure classes are **not the same** and are causally distinguishable.

### Strongest features

#### 15m distance from selected extreme

- TRUE_WRONG_DIRECTION median: ~0.107%
- RIGHT_THEN_FAILURE median: ~0.298%

Separation:

**0.438**

Median chronological-fifth separation:

**0.426**

Minimum fifth:

**0.365**

#### 30m distance from selected extreme

- TRUE_WRONG_DIRECTION: ~0.111%
- RIGHT_THEN_FAILURE: ~0.306%

Separation:

**0.436**

Minimum chronological-fifth separation:

**0.396**

This is exceptionally stable relative to prior WD discovery work.

### Other stable differentiators

RIGHT_THEN_FAILURE generally has higher:

- 15m selected-side momentum,
- selected score,
- score momentum component,
- market-relative 15m overextension,
- 30m relative overextension,
- overheat pressure,
- micro reversal pressure.

TRUE_WRONG_DIRECTION is often closer to the selected-side local extreme at entry and has a different micro candle state.

This validates the WD-5G diagnosis:

> The detector should distinguish fundamentally wrong direction from a correct-but-late/overheated continuation.

---

## Why this changes the Stage 2 architecture

A flat selective gate would try:

```text
VALID_WINNER
vs
everything else
```

Stage 1 shows that this collapses three very different rejection problems into one target.

The more defensible architecture is:

```text
Candidate trade
      |
      v
TRUE-WRONG HEAD
      |
      +-- likely wrong -> BLOCK / reversal research
      |
      v
STALL / NO-EDGE HEAD
      |
      +-- likely stall -> NO TRADE
      |
      v
LIFECYCLE-FAILURE / OVERHEAT HEAD
      |
      +-- likely right-then-fail -> NO TRADE / delay
      |
      v
HIGH-CONFIDENCE VALID WINNER
      |
      -> ENTRY
```

This matches the user's selective objective:

> fewer trades is acceptable if the retained trades have materially higher WIN precision.

---

## Stage 1 status

- full cohort labeled: **2,175 / 2,175**
- full pre-entry micro data: **2,175 / 2,175**
- full OI history: **2,175 / 2,175**
- portable feature space: **207 features**
- tests: **72 / 72 PASS**
- production changes: **none**

Formal conclusion:

`DIRECT_BINARY_WEAK_PAIRWISE_STRONG`

## Frozen artifacts

### Pre-entry micro cache

`/opt/core-app/data/wd5h1_preentry_1m_cache.jsonl`

SHA256:

`0db734fc915d476f5879846fe5f5110aaceb53a7b9f8887d12d4efed97c579e8`

### Benchmark cache

`/opt/core-app/data/wd5h1_benchmark_1m_cache.json`

SHA256:

`0b9ea95e5e58949f4cf995a0db72a004109cbb10391a13006624a9e91168f659`

### OI cache

`/opt/core-app/data/wd5h1_oi_5m_cache.jsonl`

SHA256:

`f7cc3a99a16b9f715e12b2f49cd25684f09c9fe6b770ed2de7c4526ff05ca5a5`

### Full labeled feature dataset

`/opt/core-app/data/wd5h1_thesis_labeled_features.csv`

SHA256:

`8b373ba828c24ef40c12b30a2b14ae1f48aec44b15877f79967046c683bf993a`

### Full feature audit

`/opt/core-app/data/wd5h1_feature_audit_results.json`

SHA256:

`fa6966c02b69807f8d96157a86157ad5a25ff7f186063389ab29a6cca4c6c74b`

## Handoff

Next:

**WD-5H Stage 2 — Chronological Hierarchical Thesis Classifier + High-Precision WIN Abstention Gate**

The next stage should:

1. use train-only feature selection,
2. build separate rejection heads,
3. combine them into a final `TAKE / ABSTAIN` gate,
4. optimize WIN precision first,
5. measure coverage, WR, PnL, trade/day, runner retention, and unseen-symbol performance,
6. leave final chronological test untouched during threshold selection.
