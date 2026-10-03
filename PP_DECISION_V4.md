# PP-DECISION V4 — High-Frequency Peak Capture

Status: **PLANNED / CONTRACT FROZEN / NOT ACTIVE**

PP-DECISION V4 is the successor research track to the retired V3 low-tail and Stage 2B.1 shadow paths.

It exists to answer one question:

> Can materially higher causal observation resolution compress the full peak-capture distribution — especially the <80% lower tail — before any new exit/protection logic is engineered?

V4 does **not** assume that the future peak is knowable in real time.

## Authority

At Step 3:

- V4 has **no startup loop**;
- V4 has **no API endpoint**;
- V4 has **no environment flag**;
- V4 has **no paper authority**;
- V4 has **no live authority**;
- V4 does **not** change Stage 12;
- V4 does **not** change the current 15-second fast guard.

This file freezes only the research namespace, definitions, stages, and promotion gates.

## Why V4 exists

The retired V3 track established:

- clean terminal cohort: **1,196** trades;
- median terminal observed peak / true MFE: **90.17%**;
- mean capture: **86.33%**;
- >=90% share: **50.42%**;
- <80% share: **25.67%**;
- **306 / 307** trades below 80% were dominated by favorable excursions occurring between ~15-second current-price observations;
- universal trailing destroyed runners;
- selective 15-second protection also failed to reduce the <80% tail;
- the retired Stage 2B.1 lane proved that ~5-second sampling infrastructure was operational, but that lane has been shut down and archived.

Therefore V4 starts from a different premise:

> Improve causal price-path observability first. Do not tune another protection formula until the information layer itself proves materially better.

## Core definitions

- **True MFE**: offline favorable-excursion benchmark reconstructed after close. Never a runtime input.
- **Observable peak**: maximum executable/current price PnL actually sampled by the active V4 observation mechanism.
- **Observation resolution**: actual time between successive causal executable-price observations.
- **Capture ratio**: observable peak / true MFE for observability stages; later realized exit / true MFE only after an execution stage exists.
- **Low tail**: capture ratio <80%.
- **High capture**: capture ratio >=90%.
- **Runner**: a trade whose favorable excursion continues materially after an earlier local peak/retracement.

## Non-negotiable design rules

1. **One active V4 observation mechanism only.**
   - No parallel 5s shadow plus separate production peak observer.
   - No duplicate polling lanes measuring the same thing.

2. **Observation before protection.**
   - V4 must first prove a better observable-peak distribution.
   - No new trailing/profit-protection formula is promoted during V4-1 to V4-3.

3. **Executable prices only for causal observable peaks.**
   - Current/tick/exchange event prices may count as observed.
   - Candle high/low is an offline benchmark or trigger-touch diagnostic, not an executable observed peak unless the exchange mechanism itself actually observed/acted on it.

4. **No future leakage.**
   - True MFE and terminal-vs-continuation labels are offline labels only.

5. **No synthetic backfill.**
   - Missing historical high-frequency observations are not reconstructed as if they had been observed live.

6. **Explicit activation boundary.**
   - When V4 is eventually activated, only positions/events after the frozen boundary may enter the prospective cohort.

7. **Distributional success criteria.**
   - Median alone is insufficient.
   - V4 must report mean, median, P10, P25, >=90% share, <80% share, and chronological stability.

8. **Runner preservation remains a separate gate.**
   - Better visibility is not permission to exit every local peak.

## Data-source contract

Step 3 intentionally does **not** activate or hard-code a new provider/runtime source.

When V4-1 is implemented, it must expose one canonical observation stream to downstream logic. If more than one market-data API/provider is used for resilience or cross-checking, they must feed that **single canonical stream** rather than create parallel competing peak observers.

Provider selection, fallback behavior, timestamp normalization, duplicate suppression, and disagreement handling must be frozen before V4-1 activation.

## Roadmap

### V4-0 — Namespace & Contract ✅ COMPLETE

Purpose:
- open the new namespace;
- freeze definitions and gates;
- explicitly separate V4 from retired V3 paths;
- make no runtime change.

Artifacts:
- `PP_DECISION_V4.md`
- `docs/research/profit_protection_v4/PP_V4_HIGH_FREQUENCY_PEAK_CAPTURE_CONTRACT.md`
- `research/profit_protection_v4/README.md`

### V4-1 — High-Frequency Observability Benchmark ⏳ NOT STARTED

First active experiment.

Goal:
- collect one canonical higher-frequency executable-price path;
- initial target cadence begins at approximately **5 seconds** unless the implementation contract selects an event-driven mechanism;
- compare the new observed peak against the existing historical 15-second benchmark and offline true MFE.

Required output:
- actual cadence distribution;
- data gaps/error rate;
- observable peak / true MFE distribution;
- >=80%, >=90%, >=95% shares;
- P10/P25;
- chronology by early/mid/late cohort;
- per-side and volatility diagnostics.

No exit authority.

### V4-2 — 5s/Event Path vs 15s Benchmark ⏳ BLOCKED ON V4-1

Use matched trades only.

Required comparison:
- old ~15s observable peak;
- V4 high-frequency observable peak;
- true MFE.

Primary question:

> Did higher-frequency observation materially recover favorable excursions that the 15-second path missed?

No protection tuning.

### V4-3 — Lower-Tail Compression Gate ⏳ BLOCKED ON V4-2

Explicitly test whether the information layer fixes the problem that killed V3.

Baseline reference from frozen V3 terminal cohort:
- >=90% share: **50.42%**
- <80% share: **25.67%**
- P10: **67.99%**
- P25: **79.48%**

V4-3 must determine whether the new path:
- materially increases >=90% share;
- materially reduces <80% share;
- improves P10/P25;
- is stable chronologically;
- does not achieve apparent improvement through benchmark mismatch or missing-data selection.

If lower-tail compression is not material, V4 protection engineering remains blocked.

### V4-4 — Protection + Runner Engineering ⛔ BLOCKED ON V4-3 PASS

Only after observability improves materially:
- engineer state-dependent profit protection;
- preserve continuation runners;
- evaluate actual exit economics with fees/slippage;
- use chronological tuning/holdout;
- never optimize directly against future MFE in runtime.

## Promotion gates

### V4-1 data-quality gate

Required before analysis:
- stable timestamping;
- bounded missing observations;
- no duplicate observations counted as independent samples;
- explicit source/fallback provenance;
- sample cadence measured from actual timestamps, not configuration alone.

### V4-2 observability gate

A matched-trade comparison must show a material improvement over the old ~15s path. Exact promotion threshold will be preregistered before V4-1 activation and must not be chosen after seeing results.

### V4-3 distribution gate

The new information layer must improve the **distribution**, not just the median.

A pass requires all of:
- >=90% share improves;
- <80% share declines;
- P10 improves;
- P25 improves;
- no major chronological cohort collapses.

The exact minimum effect sizes must be frozen before the prospective evaluation.

### V4-4 protection gate

Any later protection policy must improve realized/counterfactual economics while preserving runners and respecting execution constraints.

## Relationship to archived V3 evidence

Do not delete or rewrite:

- `research/profit_protection_v3/archive/low_tail_15s/`
- `research/profit_protection_v3/archive/stage2b1_5s_shadow/`
- historical table `pp_v3_fast_peak_observations`

Those artifacts are controls and failure evidence.

They may be used for historical comparison, but they must not be silently reactivated as V4 runtime components.

## Step 3 completion condition

Step 3 is complete when:

- the V4 namespace exists;
- this contract is merged;
- README/source-of-truth links exist;
- active runtime contains **zero PP_V4 startup hooks, endpoints, env flags, or loops**;
- Stage 12 remains unchanged.

At that point V4-1 may be designed, but it is still not active.
