# PP V4-1H — Historical Matched 5s vs 15s Benchmark

Status: **COMPLETE — RETROSPECTIVE DIAGNOSTIC; MFE-BASED GATES PARTIALLY SUPERSEDED BY V4-1I**

Frozen historical 5-second cutoff: `1791043570111`

> **V4-1I correction:** Stage1I established that historical Stage12 lifecycle MFE can inherit pre-entry rolling 1m extrema. Therefore the directional 5s-vs-15s observation result remains useful, but MFE-based promotion/gate interpretation in this report must not be used until clean post-entry MFE labels are rebuilt. See `PP_V4_STAGE1I_5S_FAILURE_ANATOMY.md`.

Source of truth:
- script: `research/profit_protection_v4/stage1h_historical_matched_benchmark.py`
- frozen result: `research/profit_protection_v4/results/stage1h_historical_matched_benchmark_1791043570111.json`

## Question

Does a causal ~5-second current-price observation stream recover materially more favorable excursion than the existing ~15-second observation stream on the **same trades**?

## Population

Raw matched closed PAPER positions with:
- archived Stage 2B.1 5s observations;
- PP-V2 ~15s observations;
- lifecycle true-MFE label:

**208 trades**

Of these:
- true MFE >= +0.30%: **138**
- strict full-lifecycle timing coverage: **124**

The strict cohort requires:
- 5s first sample <= 6s after entry;
- 5s last in-lifecycle sample <= 6s before close;
- 15s first sample <= 20s after entry;
- 15s last in-lifecycle sample <= 20s before close;
- peak observations restricted to the position lifetime `[open, close]`.

This removes the misleading cases where the retired 5s observer stopped while the position continued trading.

## Main result

| Metric | ~15s | ~5s | Delta |
|---|---:|---:|---:|
| Mean capture | 62.07% | 67.27% | **+5.20 pp** |
| Median capture | 82.00% | 87.03% | **+5.03 pp** |
| Aggregate peak / true MFE | 68.37% | 72.31% | **+3.94 pp** |
| P10 | 1.98% | 5.96% | **+3.97 pp** |
| P25 | 19.92% | 23.23% | **+3.30 pp** |
| >=80% share | 51.61% | 57.26% | **+5.65 pp** |
| >=90% share | 34.68% | 43.55% | **+8.87 pp** |
| >=95% share | 20.97% | 35.48% | **+14.52 pp** |
| <80% share | 48.39% | 42.74% | **-5.65 pp** |

## Per-trade effect

Among the 124 strict matched trades:
- **66 improved**
- **52 tied**
- **6 worsened**

Median per-trade delta: **+0.98 pp**.

The distribution-level improvement is larger than the median per-trade delta because a smaller set of trades gains materially from the denser observation stream.

## Rescue analysis

From the old ~15s stream:
- 60 trades were below 80%;
- **7 / 60** moved to >=80% under 5s;
- **2 / 60** moved directly to >=90%;
- 81 trades were below 90%;
- **12 / 81** moved to >=90%;
- only **1** old >=90% trade fell below90% in the 5s sample.

## Chronological stability

The 5s direction is positive across all chronological thirds.

EARLY:
- median +4.46 pp
- >=90 share +9.76 pp
- <80 reduction 4.88 pp
- aggregate +3.14 pp

MID:
- median +1.92 pp
- >=90 share +7.32 pp
- <80 reduction 4.88 pp
- aggregate +3.72 pp

LATE:
- median +4.84 pp
- >=90 share +9.52 pp
- <80 reduction 7.14 pp
- aggregate +4.80 pp

Unlike the rejected 15s selective-protection Stage C, the historical 5s observability uplift does **not** collapse in the LATE third.

## LONG vs SHORT

LONG (76):
- median +4.62 pp
- >=90 share +10.53 pp
- <80 reduction +9.21 pp
- aggregate +4.05 pp

SHORT (48):
- median +3.69 pp
- >=90 share +6.25 pp
- <80 reduction **0.00 pp**
- aggregate +3.80 pp

The remaining lower-tail problem is therefore more persistent on SHORT trades.

## Early-peak sensitivity

For trades whose final MFE was first discovered within the first 25% of trade duration (23 trades):
- median capture uplift: **+22.40 pp**
- >=90 share: **+17.39 pp**
- <80 reduction: **+13.04 pp**

This strongly supports the original V3 diagnosis that short-lived favorable excursions between 15-second samples were a major source of lost observability.

## Cadence quality

Strict cohort:
- first 5s sample after entry median: **2.85s**
- first 5s sample P90: **4.85s**
- last 5s sample before close median: **2.81s**
- last 5s sample P90: **4.44s**
- median trade-level 5s sample gap: **4,999 ms**
- P90 trade-level median gap: **5,004.1 ms**
- median 5s observations/trade: **113**
- median 15s observations/trade: **38**

## Gate diagnostic

Using the already-preregistered V4 thresholds as a **diagnostic only**:

V4-2 direction:
- median capture uplift >= +3 pp: **PASS**
- aggregate capture uplift >= +3 pp: **PASS**

V4-3 distribution:
- >=90 share uplift >= +5 pp: **PASS**
- <80 reduction >= 5 pp: **PASS**
- P10 uplift >= +5 pp: **FAIL** (+3.97 pp)
- P25 uplift >= +3 pp: **PASS**

Therefore:

> Historical evidence supports the move from ~15s to ~5s observation resolution, but 5s alone does **not** yet prove that the low-tail problem is solved.

## Decision

- Keep the active prospective V4-1 5s observer running unchanged.
- Do **not** promote any protection/exit logic from this retrospective result.
- Use prospective V4-1 to confirm the historical direction.
- The main unresolved metric is **P10**.
- If prospective 5s confirms the same pattern but P10 remains below target, the next information-layer experiment should test whether sub-5s/event-driven observation is required rather than immediately tuning a protection formula.
